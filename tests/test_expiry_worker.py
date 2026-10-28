"""Controlled worker cycles, real PostgreSQL release/metrics and signal behavior."""

import json
import os
import signal
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from pathlib import Path
from threading import Event
from unittest.mock import patch

import yaml
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import (
    DatabaseError,
    OperationalError,
    close_old_connections,
    connection,
    connections,
    transaction,
)
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from accounts.models import User
from inventory.models import Stock, StockMovement
from orders.models import Order
from orders.reservations import expire_due_reservations
from orders.worker import backlog_observation, stop_on_signals

from .test_reservation_expiry import ReservationExpiryFixture

MODULE = "orders.management.commands.run_reservation_expiry"


class WorkerConfigurationTests(SimpleTestCase):
    def test_invalid_bounds_fail_before_installing_signal_handlers(self):
        for options in [
            {"interval_seconds": 0},
            {"interval_seconds": 3601},
            {"limit": 0},
            {"limit": 1001},
            {"max_cycles": 0},
            {"max_cycles": 10001},
        ]:
            with (
                self.subTest(options=options),
                patch(MODULE + ".stop_on_signals") as handlers,
                self.assertRaises(CommandError),
            ):
                call_command(
                    "run_reservation_expiry",
                    expected_database="olist_demo",
                    actor_email="admin@example.com",
                    stdout=StringIO(),
                    **options,
                )
            handlers.assert_not_called()

    def test_real_term_int_only_signal_event_and_restore_handlers_on_error(self):
        previous = {number: signal.getsignal(number) for number in [signal.SIGTERM, signal.SIGINT]}
        event = Event()
        with self.assertRaisesRegex(RuntimeError, "controlled"):
            with stop_on_signals(event):
                for number in previous:
                    event.clear()
                    os.kill(os.getpid(), number)
                    self.assertTrue(event.is_set())
                raise RuntimeError("controlled context exit")
        for number, handler in previous.items():
            self.assertEqual(signal.getsignal(number), handler)

    def test_worker_is_opt_in_and_has_no_shared_mounts_or_published_port(self):
        root = Path(__file__).resolve().parents[1]
        base = yaml.safe_load((root / "compose.yaml").read_text())
        overlay = yaml.safe_load((root / "compose.worker.yaml").read_text())
        self.assertEqual(set(base["services"]), {"db", "app", "migrate", "importer", "tests"})
        self.assertEqual(set(overlay["services"]), {"expiry-worker"})
        worker = overlay["services"]["expiry-worker"]
        self.assertEqual(worker["profiles"], ["workers"])
        self.assertFalse(worker.get("ports"))
        self.assertFalse(worker.get("volumes"))
        self.assertEqual(worker["environment"]["PGUSER"], "olist_api")
        self.assertEqual(worker["restart"], "no")
        self.assertTrue(worker["read_only"] and worker["init"])


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ExpiryWorkerTests(ReservationExpiryFixture, TransactionTestCase):
    def run_worker(self, *, maximum=1, wait=None, batch=None, metrics=None, target=None):
        out = StringIO()
        event = Event()
        with (
            patch(MODULE + ".Command.confirm_target", side_effect=target) as guard,
            patch(MODULE + ".Event", return_value=event),
            patch.object(event, "wait", side_effect=wait or (lambda _: False)) as delay,
            patch(
                MODULE + ".expire_due_reservations", side_effect=batch or expire_due_reservations
            ) as batches,
            patch(MODULE + ".backlog_observation", side_effect=metrics or backlog_observation),
        ):
            error = None
            try:
                call_command(
                    "run_reservation_expiry",
                    expected_database=connection.settings_dict["NAME"],
                    actor_email=self.admin.email,
                    max_cycles=maximum,
                    stdout=out,
                )
            except CommandError as caught:
                error = caught
        return (
            [json.loads(line) for line in out.getvalue().splitlines()],
            error,
            guard,
            delay,
            batches,
        )

    def finished(self, events):
        return [event for event in events if event["event"] == "cycle_finished"]

    def test_backlog_excludes_legacy_future_and_terminal_orders(self):
        expired = self.due(self.buy())
        self.sweep()
        due = [self.due(self.buy()) for _ in range(2)]
        self.buy()
        legacy = self.buy()
        Order.objects.filter(pk=legacy.pk).update(reservation_expires_at=None)
        metrics = backlog_observation()
        self.assertEqual(metrics["due_pending_count"], 2)
        self.assertEqual(metrics["oldest_deadline"], due[0].reservation_expires_at.isoformat())
        self.assertGreaterEqual(metrics["oldest_overdue_seconds"], 1800)
        self.assertTrue(metrics["observation_only"])
        self.assertEqual(Order.objects.get(pk=expired.pk).status, "EXPIRED")

    def test_backlog_includes_a_locked_due_row_using_a_separate_connection(self):
        order = self.due(self.buy())

        def observe():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    pid = cursor.fetchone()[0]
                return pid, backlog_observation()
            finally:
                connections.close_all()

        with transaction.atomic(), ThreadPoolExecutor(max_workers=1) as pool:
            Order.objects.select_for_update().get(pk=order.pk)
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                holder = cursor.fetchone()[0]
            observer, result = pool.submit(observe).result(timeout=5)
            self.assertNotEqual(holder, observer)
            self.assertEqual(result["due_pending_count"], 1)
            print(
                "PostgreSQL worker backlog: "
                + json.dumps(
                    {
                        "holder_backend_pid": holder,
                        "observer_backend_pid": observer,
                        "locked_row_included": True,
                    }
                ),
                flush=True,
            )

    def test_term_during_controlled_postgresql_release_finishes_only_current_order(self):
        first, second = self.due(self.buy()), self.due(self.buy())
        stop = Event()
        fired = []

        def signal_before_release(execute, sql, params, many, context):
            if sql.startswith('INSERT INTO "inventory_stock_movement"') and not fired:
                self.assertTrue(connection.in_atomic_block)
                fired.append(True)
                os.kill(os.getpid(), signal.SIGTERM)
            return execute(sql, params, many, context)

        with stop_on_signals(stop), connection.execute_wrapper(signal_before_release):
            report = expire_due_reservations(actor=self.admin, should_stop=stop.is_set)
        self.assertTrue(fired and report["stopped"])
        self.assertEqual(report["expired_order_ids"], [first.pk])
        self.assertEqual(Order.objects.get(pk=second.pk).status, "PENDING_PAYMENT")
        self.assertEqual(Stock.objects.get(offer=self.offer).available_quantity, 9)
        self.assertEqual(StockMovement.objects.filter(movement_type="RELEASE").count(), 1)
        print(
            "PostgreSQL worker stop: "
            + json.dumps(
                {
                    "signal_during_atomic_release": True,
                    "current_order_committed": True,
                    "next_order_unmodified": True,
                }
            ),
            flush=True,
        )

    def test_empty_backlog_is_zero_with_null_oldest_not_an_unavailable_observation(self):
        result = backlog_observation()
        self.assertEqual(result["due_pending_count"], 0)
        self.assertIsNone(result["oldest_deadline"])
        self.assertIsNone(result["oldest_overdue_seconds"])

    def test_finite_cycles_use_fixed_delay_fresh_connections_and_local_timeouts(self):
        order = self.due(self.buy())
        pids, timeouts = [], []

        def batch(**kwargs):
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_backend_pid(),current_setting('lock_timeout'),"
                    "current_setting('statement_timeout')"
                )
                pid, lock, statement = cursor.fetchone()
            pids.append(pid)
            timeouts.append((lock, statement))
            return expire_due_reservations(**kwargs)

        events, error, guard, delay, _ = self.run_worker(maximum=2, batch=batch)
        self.assertIsNone(error)
        self.assertEqual(guard.call_count, 2)
        delay.assert_called_once_with(60)
        self.assertEqual(len(set(pids)), 2)
        self.assertEqual(timeouts, [("5s", "15s"), ("5s", "15s")])
        self.assertEqual([e["batch"]["expired_count"] for e in self.finished(events)], [1, 0])
        self.assertEqual(events[-1]["reason"], "limit")
        self.assertEqual(Order.objects.get(pk=order.pk).status, "EXPIRED")
        with connection.cursor() as cursor:
            cursor.execute("SHOW lock_timeout")
            self.assertEqual(cursor.fetchone()[0], "0")

    def test_database_failure_retries_after_delay_without_leaking_details(self):
        attempts = []

        def batch(**kwargs):
            attempts.append(True)
            if len(attempts) == 1:
                raise OperationalError("private password DSN")
            return expire_due_reservations(**kwargs)

        events, error, guard, delay, _ = self.run_worker(maximum=2, batch=batch)
        self.assertIsNone(error)
        self.assertEqual(guard.call_count, 2)
        delay.assert_called_once_with(60)
        finished = self.finished(events)
        self.assertEqual([e["outcome"] for e in finished], ["database_error", "ok"])
        self.assertIsNone(finished[0]["batch"])
        self.assertIsNone(finished[0]["backlog"])
        self.assertNotIn("private", json.dumps(events))

    def test_metrics_failure_keeps_known_committed_count_and_missing_backlog(self):
        order = self.due(self.buy())

        def metrics():
            raise DatabaseError("private SQL")

        events, error, _, _, _ = self.run_worker(metrics=metrics)
        self.assertIsInstance(error, CommandError)
        result = self.finished(events)[0]
        self.assertEqual(result["outcome"], "database_error")
        self.assertEqual(result["batch"]["expired_count"], 1)
        self.assertIsNone(result["backlog"])
        self.assertEqual(Order.objects.get(pk=order.pk).status, "EXPIRED")

    def test_partial_failure_remains_visible_and_never_retries_without_delay(self):
        corrupt, valid = self.due(self.buy()), self.due(self.buy())
        Order.objects.filter(pk=corrupt.pk).update(total="999.00")
        events, error, _, delay, _ = self.run_worker(maximum=2)
        self.assertIsInstance(error, CommandError)
        delay.assert_called_once_with(60)
        finished = self.finished(events)
        self.assertEqual([e["outcome"] for e in finished], ["partial_failure"] * 2)
        self.assertEqual(finished[0]["batch"]["expired_count"], 1)
        self.assertEqual(finished[0]["batch"]["failure_codes"], {"integrity_conflict": 1})
        self.assertEqual(Order.objects.get(pk=valid.pk).status, "EXPIRED")

    def test_revoked_actor_stops_next_cycle_without_another_batch(self):
        def revoke(_):
            User.objects.filter(pk=self.admin.pk).update(is_active=False)
            return False

        events, error, guard, delay, batches = self.run_worker(maximum=3, wait=revoke)
        self.assertIsInstance(error, CommandError)
        self.assertEqual((guard.call_count, batches.call_count, delay.call_count), (2, 1, 1))
        self.assertEqual(self.finished(events)[-1]["outcome"], "authorization_error")

    def test_target_failure_is_fatal_and_not_retried(self):
        def wrong(_):
            raise CommandError("Confirm target.")

        events, error, guard, delay, batches = self.run_worker(maximum=3, target=wrong)
        self.assertIsInstance(error, CommandError)
        self.assertEqual(guard.call_count, 1)
        delay.assert_not_called()
        batches.assert_not_called()
        self.assertEqual(self.finished(events)[0]["outcome"], "target_error")

    def test_real_test_database_role_cannot_run_worker(self):
        with self.assertRaises(CommandError):
            call_command(
                "run_reservation_expiry",
                expected_database=connection.settings_dict["NAME"],
                actor_email=self.admin.email,
                max_cycles=1,
                stdout=StringIO(),
            )

    def test_term_during_wait_stops_normally_and_restores_previous_handlers(self):
        previous = signal.getsignal(signal.SIGTERM)

        def terminate(_):
            os.kill(os.getpid(), signal.SIGTERM)
            return True

        events, error, _, delay, batches = self.run_worker(maximum=10, wait=terminate)
        self.assertIsNone(error)
        self.assertEqual((delay.call_count, batches.call_count), (1, 1))
        self.assertEqual((events[-1]["reason"], events[-1]["stop_requested"]), ("signal", True))
        self.assertEqual(signal.getsignal(signal.SIGTERM), previous)

    def test_outer_transaction_is_rejected_without_closing_it(self):
        with transaction.atomic(), self.assertRaises(CommandError):
            call_command(
                "run_reservation_expiry",
                expected_database=connection.settings_dict["NAME"],
                actor_email=self.admin.email,
                max_cycles=1,
                stdout=StringIO(),
            )

    def test_unexpected_failure_is_not_mislabeled_or_retried(self):
        def broken(**kwargs):
            raise ValueError("private implementation details")

        events, error, guard, delay, batches = self.run_worker(maximum=3, batch=broken)
        self.assertIsInstance(error, CommandError)
        self.assertEqual((guard.call_count, batches.call_count), (1, 1))
        delay.assert_not_called()
        self.assertEqual(self.finished(events)[0]["outcome"], "unexpected_error")
        self.assertNotIn("private", json.dumps(events))
