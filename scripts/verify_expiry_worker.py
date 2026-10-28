"""Observe real worker cycles/restarts/SIGTERM on one new isolated fictional fixture."""

import argparse
import json
import os
import re
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from scripts.verify_curl import ROOT, require


def validate_target(identity, running):
    if identity != ["olist_demo", "olist_api", 0, 4, 5, 3, 10] or running:
        raise ValueError("Use a fresh source-free seeded review database with no worker container.")


def json_events(output):
    return [json.loads(line) for line in output.splitlines() if line.startswith("{")]


def verify(compose, environment, report):
    def run(*arguments, expected=0):
        result = subprocess.run(
            [*compose, *arguments], cwd=ROOT, env=environment, capture_output=True, text=True
        )
        report["commands"].append(
            {
                "command": [*compose, *arguments],
                "exit_code": result.returncode,
                "expected": expected,
            }
        )
        require(
            result.returncode == expected,
            "Worker verification command failed; inspect private state.",
        )
        return result.stdout

    probe = (
        "import django,json;django.setup();from django.db import connection;"
        "c=connection.cursor();c.execute('SELECT current_database(),current_user,"
        "(SELECT COUNT(*) FROM olist_order),(SELECT COUNT(*) FROM accounts_user),"
        "(SELECT COUNT(*) FROM orders_order),(SELECT COUNT(*) FROM catalog_offer),"
        "(SELECT COUNT(*) FROM inventory_stock_movement)');print(json.dumps(c.fetchone()))"
    )
    identity = json.loads(run("run", "--rm", "--entrypoint", "python", "app", "-c", probe))
    running = run("ps", "--all", "--quiet", "expiry-worker").strip()
    validate_target(identity, running)
    report["initial_identity"] = identity
    prepare = """import django,json;django.setup()
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from accounts.models import User
from catalog.models import Offer
from orders.demo import ADDRESS
from orders.models import Order
from orders.services import create_order
from orders.worker import backlog_observation
from inventory.models import StockMovement
with transaction.atomic():
 offer=Offer.objects.order_by('id').first()
 order=create_order(actor=User.objects.get(email='customer1@example.com'),
  items=[{'offer_id':offer.pk,'quantity':1}],shipping_address=dict(ADDRESS))
 created=timezone.now()-timedelta(hours=1)
 Order.objects.filter(pk=order.pk).update(created_at=created,
  reservation_expires_at=created+timedelta(minutes=30))
 StockMovement.objects.filter(order=order,movement_type='RESERVATION').update(
  created_at=created+timedelta(microseconds=1))
print(json.dumps({'new_order_id':order.pk,'before_worker':backlog_observation()}))
"""
    report["fixture"] = json.loads(
        run("run", "--rm", "--entrypoint", "python", "app", "-c", prepare)
    )
    require(
        report["fixture"]["before_worker"]["due_pending_count"] == 1, "Fixture backlog differs."
    )
    finite = json_events(
        run(
            "run",
            "--rm",
            "expiry-worker",
            "run_reservation_expiry",
            "--expected-database",
            "olist_demo",
            "--actor-email",
            "admin@example.com",
            "--interval-seconds",
            "1",
            "--max-cycles",
            "2",
        )
    )
    finished = [event for event in finite if event["event"] == "cycle_finished"]
    require(
        len(finished) == 2 and all(e["outcome"] == "ok" for e in finished), "Finite cycles failed."
    )
    require(
        [e["batch"]["expired_count"] for e in finished] == [1, 0], "Repeated cycle released again."
    )
    require(all(e["backlog"]["due_pending_count"] == 0 for e in finished), "Backlog not cleared.")
    report["finite_events"] = finite
    sessions = []
    try:
        for session in range(2):
            run("up", "-d", "expiry-worker")
            deadline = time.monotonic() + 30
            observed = None
            while time.monotonic() < deadline:
                events = json_events(run("logs", "--no-color", "--no-log-prefix", "expiry-worker"))
                starts = [i for i, e in enumerate(events) if e["event"] == "worker_started"]
                current = events[starts[-1] :] if len(starts) > session else []
                if any(e["event"] == "cycle_finished" for e in current):
                    observed = current
                    break
                time.sleep(0.1)
            require(observed is not None, "No completed worker cycle was observed.")
            # Stop only after an actual completion event, during the 60-second interval.
            run("stop", "expiry-worker")
            container = run("ps", "--all", "--quiet", "expiry-worker").strip()
            result = subprocess.run(
                ["docker", "inspect", container, "--format", "{{.State.ExitCode}}"],
                env=environment,
                capture_output=True,
                text=True,
                check=True,
            )
            require(result.stdout.strip() == "0", "Worker did not stop normally.")
            all_events = json_events(run("logs", "--no-color", "--no-log-prefix", "expiry-worker"))
            index = [i for i, e in enumerate(all_events) if e["event"] == "worker_started"][-1]
            stopped = all_events[index:]
            require(
                stopped[-1]["event"] == "worker_stopped" and stopped[-1]["reason"] == "signal",
                "SIGTERM was not handled.",
            )
            require(
                all(
                    e["batch"]["expired_count"] == 0
                    for e in stopped
                    if e["event"] == "cycle_finished"
                ),
                "Restart released stock twice.",
            )
            sessions.append({"events": stopped, "container_exit_code": 0})
    finally:
        # Only the explicitly named review service is stopped; volumes are retained.
        subprocess.run(
            [*compose, "stop", "expiry-worker"],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            check=True,
        )
    report["signal_sessions"] = sessions
    final_probe = """import django,json,sys;django.setup()
from orders.models import Order
from orders.worker import backlog_observation
from inventory.models import StockMovement
order=Order.objects.get(pk=int(sys.argv[1]))
print(json.dumps({'status':order.status,'release_count':StockMovement.objects.filter(
 order=order,movement_type='RELEASE').count(),'backlog':backlog_observation()}))
"""
    report["final_state"] = json.loads(
        run(
            "run",
            "--rm",
            "--entrypoint",
            "python",
            "app",
            "-c",
            final_probe,
            str(report["fixture"]["new_order_id"]),
        )
    )
    require(
        report["final_state"]["status"] == "EXPIRED"
        and report["final_state"]["release_count"] == 1,
        "Final expiry audit differs.",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-new-fixture-time-travel", action="store_true")
    args = parser.parse_args()
    if not args.allow_new_fixture_time_travel or not re.fullmatch(
        r"olist-worker-review(?:-[a-z0-9]+)?", args.project
    ):
        parser.error(
            "Use an isolated worker-review project and explicitly allow fixture time travel."
        )
    if args.output.exists():
        raise FileExistsError("Preserve previous evidence; choose a new filename.")
    environment = {k: v for k, v in os.environ.items() if not k.startswith("COMPOSE_")}
    compose = [
        "docker",
        "compose",
        "--project-directory",
        str(ROOT),
        "-p",
        args.project,
        "--env-file",
        str(args.env_file.resolve()),
        "-f",
        str(ROOT / "compose.yaml"),
        "-f",
        str(ROOT / "compose.worker.yaml"),
        "--profile",
        "workers",
    ]
    report = {
        "started_at_utc": datetime.now(UTC).isoformat(),
        "passed": False,
        "project": args.project,
        "commands": [],
        "fixture_time_travel": (
            "Only a new fictional purchase/reservation is shifted one hour; "
            "no real 30-minute wait is claimed."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        try:
            verify(compose, environment, report)
            report["passed"] = True
        except Exception:
            report["failure"] = (
                "Worker verification failed; inspect the private isolated environment."
            )
            raise RuntimeError(report["failure"]) from None
        finally:
            report["finished_at_utc"] = datetime.now(UTC).isoformat()
            json.dump(report, output, indent=2)
            output.write("\n")
    print("Verified two finite cycles, two observed SIGTERM sessions and one stock release.")


if __name__ == "__main__":
    main()
