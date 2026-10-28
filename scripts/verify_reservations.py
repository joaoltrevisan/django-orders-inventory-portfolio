"""Verify expiry with real curl/CLI and explicit time travel on one new review fixture."""

import argparse
import json
import re
import secrets
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from scripts.verify_curl import CURL, ROOT, compose_output, configuration, require


def review_url(compose):
    probe = (
        "import django,json;django.setup();from django.db import connection;"
        "c=connection.cursor();c.execute('SELECT current_database(),current_user,"
        "(SELECT COUNT(*) FROM olist_order)');print(json.dumps(c.fetchone()))"
    )
    identity = json.loads(compose_output(compose, "exec", "-T", "app", "python", "-c", probe))
    if identity != ["olist_demo", "olist_api", 0]:
        raise ValueError("Expiry fixtures require a source-free isolated olist_demo API database.")
    address = compose_output(compose, "port", "app", "8000")
    if not re.fullmatch(r"127\.0\.0\.1:[0-9]{1,5}", address):
        raise ValueError("Expiry fixture HTTP must use one IPv4 loopback binding.")
    return "http://" + address


def workflow(compose, base, values, report):
    def request(
        name, path, *, method="GET", token=None, payload=None, expected=200, key=None, replayed=None
    ):
        config = [f"url = {json.dumps(base + path)}", f"request = {json.dumps(method)}", "include"]
        if token:
            config.append(f"header = {json.dumps('Authorization: Bearer ' + token)}")
        if key:
            config.append(f"header = {json.dumps('Idempotency-Key: ' + key)}")
        if payload is not None:
            config.extend(
                [
                    'header = "Content-Type: application/json"',
                    f"data = {json.dumps(json.dumps(payload))}",
                ]
            )
        result = subprocess.run(CURL, input="\n".join(config), capture_output=True, text=True)
        require(result.returncode == 0, "Expiry curl transport failed.")
        response, status = result.stdout.rsplit("\n", 1)
        headers, body = response.split("\n\n", 1)
        replay = next(
            (
                line.split(":", 1)[1].strip()
                for line in headers.splitlines()
                if line.lower().startswith("idempotency-replayed:")
            ),
            None,
        )
        report["requests"].append(
            {
                "name": name,
                "method": method,
                "path": path,
                "status": int(status),
                "expected": expected,
                "curl_exit_code": result.returncode,
                "idempotency_replayed": replay,
            }
        )
        require(int(status) == expected and replay == replayed, "Unexpected expiry HTTP outcome.")
        return json.loads(body)

    suffix = secrets.token_hex(6)
    email, password, key = (
        f"expiry-{suffix}@example.com",
        secrets.token_urlsafe(36),
        f"expiry-{suffix}",
    )
    admin = request(
        "administrator login",
        "/api/auth/login/",
        method="POST",
        payload={"email": "admin@example.com", "password": values["DEMO_PASSWORD"]},
    )["access"]
    request(
        "fixture customer",
        "/api/auth/register/",
        method="POST",
        expected=201,
        payload={"email": email, "name": "Fictional Expiry Buyer", "password": password},
    )
    buyer = request(
        "fixture login",
        "/api/auth/login/",
        method="POST",
        payload={"email": email, "password": password},
    )["access"]
    product = request(
        "fixture product",
        "/api/products/",
        method="POST",
        token=admin,
        expected=201,
        payload={"sku": "EXPIRY-" + suffix.upper(), "name": "Fictional Expiry Lamp"},
    )
    seller = request(
        "fixture seller",
        "/api/sellers/",
        method="POST",
        token=admin,
        expected=201,
        payload={"label": "Fictional Expiry Seller"},
    )
    offer = request(
        "fixture offer",
        "/api/offers/",
        method="POST",
        token=admin,
        expected=201,
        payload={
            "seller_id": seller["id"],
            "product_id": product["id"],
            "simulated_price": "12.50",
        },
    )
    request(
        "fixture supply",
        f"/api/inventory/{offer['id']}/changes/",
        method="POST",
        token=admin,
        expected=201,
        payload={
            "movement_type": "ENTRY",
            "quantity_delta": 5,
            "reason": "Fictional expiry verification supply.",
        },
    )
    payload = {
        "items": [{"offer_id": offer["id"], "quantity": 2}],
        "shipping_address": {
            "recipient": "Fictional Expiry Buyer",
            "street": "Example Street",
            "number": "10",
            "district": "Example",
            "city": "Example City",
            "state": "SP",
            "postal_code": "00000000",
        },
    }
    order = request(
        "keyed fixture purchase",
        "/api/orders/",
        method="POST",
        token=buyer,
        expected=201,
        key=key,
        replayed="false",
        payload=payload,
    )
    order_id = order["id"]
    # Only this newly created, owned, unprocessed order is shifted. Existing rows are not reset.
    prepare = """import django,json,sys;django.setup()
from datetime import timedelta
from django.db import connection,transaction
from django.utils import timezone
from orders.models import Order
from inventory.models import StockMovement
from olist.models import HistoricalOrder
with connection.cursor() as c:
 c.execute('SELECT current_database()');database=c.fetchone()[0]
if database!='olist_demo' or HistoricalOrder.objects.exists():
 raise RuntimeError('Wrong fixture target.')
with transaction.atomic():
 o=Order.objects.select_for_update().get(
  pk=int(sys.argv[1]),customer__user__email=sys.argv[2],
  status='PENDING_PAYMENT',expired_at__isnull=True)
 if timezone.now()-o.created_at>timedelta(minutes=5) or o.stock_movements.count()!=1:
  raise RuntimeError('Fixture is not fresh.')
 if o.items.count()!=1 or o.stock_movements.filter(movement_type='RELEASE').exists():
  raise RuntimeError('Fixture is processed.')
 created=timezone.now()-timedelta(hours=1)
 Order.objects.filter(pk=o.pk).update(
  created_at=created,reservation_expires_at=created+timedelta(minutes=30))
 StockMovement.objects.filter(order=o,movement_type='RESERVATION').update(
  created_at=created+timedelta(microseconds=1))
print(json.dumps({'prepared_order_id':o.pk,'only_new_fixture_shifted':True}))
"""
    result = subprocess.run(
        [
            *compose,
            "run",
            "--rm",
            "--entrypoint",
            "python",
            "migrate",
            "-c",
            prepare,
            str(order_id),
            email,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    require(result.returncode == 0, "Private fixture preparation failed.")
    report["fixture_preparation"] = json.loads(result.stdout)
    report["fixture_preparation"]["exit_code"] = result.returncode
    overdue = request("overdue still pending", f"/api/orders/{order_id}/", token=buyer)
    require(
        overdue["status"] == "PENDING_PAYMENT", "Time travel unexpectedly transitioned the fixture."
    )
    late = request(
        "late payment rejected",
        f"/api/orders/{order_id}/simulated-payment/",
        method="POST",
        token=admin,
        payload={},
        expected=409,
    )
    require(late["code"] == "reservation_expired", "Late payment conflict differs.")
    command = [
        "expire_reservations",
        "--expected-database",
        "olist_demo",
        "--actor-email",
        "admin@example.com",
        "--limit",
        "100",
    ]
    for name, service, expected in [
        ("owner role refused", "migrate", 1),
        ("explicit expiry", "app", 0),
        ("repeated expiry", "app", 0),
    ]:
        result = subprocess.run(
            [*compose, "run", "--rm", service, *command], cwd=ROOT, capture_output=True, text=True
        )
        require(result.returncode == expected, "Unexpected expiry command exit code.")
        entry = {
            "name": name,
            "command": [*compose, "run", "--rm", service, *command],
            "exit_code": result.returncode,
        }
        if result.returncode == 0:
            entry["report"] = json.loads(result.stdout)
            ids = entry["report"]["expired_order_ids"]
            require(
                (order_id in ids) if name == "explicit expiry" else order_id not in ids,
                "Expiry repetition changed order identity.",
            )
        if name == "owner role refused":
            require(
                "Confirm the target database and use the operational API role." in result.stderr,
                "Owner refusal did not come from the expected role guard.",
            )
            entry["role_guard_message_verified"] = True
        report["commands"].append(entry)
    expired = request("expired state", f"/api/orders/{order_id}/", token=buyer)
    replay = request(
        "expired keyed replay",
        "/api/orders/",
        method="POST",
        token=buyer,
        key=key,
        replayed="true",
        payload=payload,
    )
    require(
        expired["status"] == replay["status"] == "EXPIRED" and replay["id"] == order_id,
        "Expired replay differs.",
    )
    require(
        replay["expired_at"] == expired["expired_at"]
        and replay["reservation_expires_at"] == overdue["reservation_expires_at"],
        "Replay changed expiry timestamps.",
    )
    require(
        replay["total"] == order["total"] and replay["items"] == order["items"],
        "Expiry changed purchase snapshots.",
    )
    request(
        "expired cancellation rejected",
        f"/api/orders/{order_id}/cancel/",
        method="POST",
        token=buyer,
        payload={},
        expected=409,
    )
    request(
        "expired payment rejected",
        f"/api/orders/{order_id}/simulated-payment/",
        method="POST",
        token=admin,
        payload={},
        expected=409,
    )
    stock = request("restored fixture stock", f"/api/inventory/{offer['id']}/", token=admin)
    require(stock["available_quantity"] == 5, "Expiry restored the wrong stock.")
    movements = request(
        "exactly one fixture release", f"/api/inventory/movements/?order_id={order_id}", token=admin
    )
    require(
        movements["count"] == 2 and sum(row["quantity_delta"] for row in movements["results"]) == 0,
        "Expiry ledger differs.",
    )
    report["assertions"] = {
        "late_payment_does_not_autoexpire": True,
        "owner_role_refused": True,
        "explicit_expiry_restores_once": True,
        "keyed_replay_preserves_expired_state_and_snapshots": True,
        "all_data_simulated": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-new-fixture-time-travel", action="store_true")
    args = parser.parse_args()
    if not args.allow_new_fixture_time_travel or not re.fullmatch(
        r"olist-reservation-review(?:-[a-z0-9]+)?", args.project
    ):
        parser.error(
            "Use a dedicated olist-reservation-review project "
            "and explicitly permit new-fixture time travel."
        )
    if args.output.exists():
        raise FileExistsError("Preserve earlier evidence; choose a new filename.")
    values = configuration(args.env_file)
    compose = ["docker", "compose", "-p", args.project, "--env-file", str(args.env_file.resolve())]
    base = review_url(compose)
    report = {
        "started_at_utc": datetime.now(UTC).isoformat(),
        "passed": False,
        "project": args.project,
        "database": "olist_demo",
        "base_url": base,
        "fixture_time_travel": (
            "Explicitly shifts only a new fictional order/reservation; "
            "no waiting 30 minutes is claimed."
        ),
        "requests": [],
        "commands": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        try:
            workflow(compose, base, values, report)
            report["passed"] = True
        except Exception:
            report["failure"] = (
                "Expiry verification failed; inspect the private review environment."
            )
            raise RuntimeError(report["failure"]) from None
        finally:
            report["finished_at_utc"] = datetime.now(UTC).isoformat()
            json.dump(report, output, indent=2)
            output.write("\n")
    print(f"Passed {len(report['requests'])} real curl requests and three command checks.")


if __name__ == "__main__":
    main()
