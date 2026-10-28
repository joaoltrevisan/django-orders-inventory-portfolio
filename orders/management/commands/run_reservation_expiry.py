"""Run nonoverlapping expiry cycles with explicit target/actor and graceful stop."""

import json
import time
from datetime import UTC, datetime
from threading import Event

from django.core.exceptions import PermissionDenied
from django.core.management.base import CommandError
from django.db import DatabaseError, close_old_connections, connection

from accounts.models import User
from accounts.permissions import require_administrator
from orders.reservations import expire_due_reservations
from orders.worker import backlog_observation, batch_summary, stop_on_signals

from .expire_reservations import Command as ExpiryCommand


class Command(ExpiryCommand):
    help = "Run optional periodic simulated reservation expiry until stopped."

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("--interval-seconds", type=int, default=60)
        parser.add_argument("--max-cycles", type=int)

    def emit(self, event, **values):
        self.stdout.write(
            json.dumps(
                {"event": event, "at_utc": datetime.now(UTC).isoformat(), **values}, sort_keys=True
            )
        )

    def handle(self, *args, **options):
        interval, limit, maximum = (
            options["interval_seconds"],
            options["limit"],
            options["max_cycles"],
        )
        if (
            type(interval) is not int
            or not 1 <= interval <= 3600
            or type(limit) is not int
            or not 1 <= limit <= 1000
            or (maximum is not None and (type(maximum) is not int or not 1 <= maximum <= 10000))
        ):
            raise CommandError(
                "Use interval 1–3600, batch limit 1–1000 and optional max-cycles 1–10000."
            )
        if connection.in_atomic_block:
            raise CommandError("Run the worker outside an enclosing transaction.")
        stop = Event()
        cycles, reason = 0, "failure"
        try:
            with stop_on_signals(stop):
                self.emit(
                    "worker_started",
                    interval_seconds=interval,
                    batch_limit=limit,
                    max_cycles=maximum,
                )
                while not stop.is_set():
                    cycles += 1
                    started = time.monotonic()
                    report, backlog, fatal, outcome = None, None, False, "unexpected_error"
                    self.emit("cycle_started", cycle=cycles)
                    try:
                        close_old_connections()
                        self.confirm_target(options["expected_database"])
                        with connection.cursor() as cursor:
                            cursor.execute(
                                "SELECT set_config('lock_timeout', %s, false), "
                                "set_config('statement_timeout', %s, false)",
                                ["5s", "15s"],
                            )
                        actor = User.objects.filter(email=options["actor_email"]).first()
                        require_administrator(actor)
                        report = expire_due_reservations(
                            actor=actor, limit=limit, should_stop=stop.is_set
                        )
                        if any(row["code"] == "permission_denied" for row in report["failures"]):
                            outcome, fatal = "authorization_error", True
                        else:
                            backlog = backlog_observation()
                            outcome = "ok" if report["passed"] else "partial_failure"
                    except PermissionDenied:
                        outcome, fatal = "authorization_error", True
                    except CommandError:
                        outcome, fatal = "target_error", True
                    except DatabaseError:
                        outcome = "database_error"
                    except Exception:
                        outcome, fatal = "unexpected_error", True
                    finally:
                        connection.close()
                        self.emit(
                            "cycle_finished",
                            cycle=cycles,
                            outcome=outcome,
                            batch=batch_summary(report),
                            backlog=backlog,
                            duration_seconds=round(time.monotonic() - started, 3),
                        )
                    if fatal:
                        raise CommandError("Worker encountered a fatal error; inspect JSON events.")
                    if stop.is_set():
                        reason = "signal"
                        break
                    if maximum is not None and cycles >= maximum:
                        reason = "limit"
                        if outcome != "ok":
                            raise CommandError(
                                "The final bounded worker cycle failed; inspect JSON events."
                            )
                        break
                    if stop.wait(interval):
                        reason = "signal"
                        break
            if stop.is_set() and cycles == 0:
                reason = "signal"
        finally:
            connection.close()
            self.emit("worker_stopped", cycles=cycles, reason=reason, stop_requested=stop.is_set())
