"""Execute real curl workflows only against a confirmed isolated simulation database."""

import argparse
import json
import re
import secrets
import subprocess
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURL = [
    "curl",
    "--disable",
    "--noproxy",
    "*",
    "--silent",
    "--show-error",
    "--connect-timeout",
    "5",
    "--max-time",
    "30",
    "--write-out",
    "\n%{http_code}",
    "--config",
    "-",
]


def require(condition, message):
    """Keep verification active under Python -O and PYTHONOPTIMIZE."""
    if not condition:
        raise RuntimeError(message)


def configuration(path):
    """Read generated assignments as data, never source a shell configuration."""
    values = {}
    for line in path.read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    if values.get("PGDATABASE") != "olist_demo" or len(values.get("DEMO_PASSWORD", "")) < 24:
        raise ValueError(
            "Use a generated isolated demo configuration with a private seed password."
        )
    return values


def compose_output(compose, *arguments):
    result = subprocess.run([*compose, *arguments], cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Compose verification failed; inspect the isolated environment locally.")
    return result.stdout.strip()


def confirmed_url(compose):
    probe = (
        "import django,json;django.setup();from django.db import connection;"
        "c=connection.cursor();c.execute('SELECT current_database(),current_user,"
        "(SELECT COUNT(*) FROM olist_order),"
        "(SELECT COUNT(*) FROM accounts_user),"
        "(SELECT COUNT(*) FROM orders_order),"
        "(SELECT COUNT(*) FROM catalog_offer),"
        "(SELECT COUNT(*) FROM inventory_stock_movement)');print(json.dumps(c.fetchone()))"
    )
    database, role, historical_orders, users, orders, offers, movements = json.loads(
        compose_output(compose, "exec", "-T", "app", "python", "-c", probe)
    )
    if (database, role, historical_orders) != ("olist_demo", "olist_api", 0):
        raise ValueError("Curl writes require a source-free isolated olist_demo API database.")
    if (users, orders, offers, movements) != (4, 5, 3, 10):
        raise ValueError("Use a freshly seeded demo; populated workflow targets are never reset.")
    address = compose_output(compose, "port", "app", "8000")
    if not re.fullmatch(r"127\.0\.0\.1:[0-9]{1,5}", address):
        raise ValueError("The demo API must have a single IPv4 loopback binding.")
    return "http://" + address


def workflow(base_url, values, report):
    def request(
        name, method, path, expected=200, payload=None, token=None, key=None, replayed=None
    ):
        # Credentials remain on curl stdin and in process memory, never command arguments/evidence.
        config = [
            f"url = {json.dumps(base_url + path)}",
            f"request = {json.dumps(method)}",
            "include",
        ]
        if key is not None:
            config.append(f"header = {json.dumps('Idempotency-Key: ' + key)}")
        if token:
            config.append(f"header = {json.dumps('Authorization: Bearer ' + token)}")
        if payload is not None:
            config.extend(
                [
                    'header = "Content-Type: application/json"',
                    f"data = {json.dumps(json.dumps(payload))}",
                ]
            )
        result = subprocess.run(CURL, input="\n".join(config), capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(f"Curl transport failed during {name}.")
        response, status = result.stdout.rsplit("\n", 1)
        header_text, body = response.split("\n\n", 1)
        headers = {
            name.lower(): value.strip()
            for line in header_text.splitlines()[1:]
            if ":" in line
            for name, value in [line.split(":", 1)]
        }
        observed_replay = headers.get("idempotency-replayed")
        require(observed_replay == replayed, f"Unexpected replay header during {name}.")
        report["requests"].append(
            {
                "name": name,
                "method": method,
                "path": path,
                "curl_exit_code": result.returncode,
                "status": int(status),
                "expected": expected,
                "idempotency_replayed": observed_replay,
            }
        )
        if int(status) != expected:
            raise RuntimeError(f"Unexpected HTTP status during {name}.")
        return json.loads(body)

    suffix = secrets.token_hex(6)
    password = secrets.token_urlsafe(36)
    email = f"curl-{suffix}@example.com"
    request("health", "GET", "/health/")
    request("anonymous isolation", "GET", "/api/orders/", 401)
    profile = request(
        "registration",
        "POST",
        "/api/auth/register/",
        201,
        {
            "email": email,
            "name": "Fictional Curl Customer",
            "password": password,
        },
    )
    customer_tokens = request(
        "customer login",
        "POST",
        "/api/auth/login/",
        payload={
            "email": email,
            "password": password,
        },
    )
    buyer = customer_tokens["access"]
    refreshed = request(
        "token refresh",
        "POST",
        "/api/auth/refresh/",
        payload={
            "refresh": customer_tokens["refresh"],
        },
    )
    self_profile = request("self profile", "GET", "/api/auth/me/", token=refreshed["access"])
    require(self_profile["id"] == profile["id"], "The self profile identity differs.")
    admin = request(
        "administrator login",
        "POST",
        "/api/auth/login/",
        payload={
            "email": "admin@example.com",
            "password": values["DEMO_PASSWORD"],
        },
    )["access"]
    foreign_id = request("existing seeded orders", "GET", "/api/orders/", token=admin)["results"][
        0
    ]["id"]
    request("customer cannot manage inventory", "GET", "/api/inventory/", 403, token=buyer)
    product = request(
        "create product",
        "POST",
        "/api/products/",
        201,
        {
            "sku": f"CURL-{suffix.upper()}",
            "name": "Fictional Curl Lamp",
        },
        admin,
    )
    sellers = [
        request(
            f"create seller {n}",
            "POST",
            "/api/sellers/",
            201,
            {
                "label": f"Fictional Curl Seller {n}",
            },
            admin,
        )
        for n in [1, 2]
    ]
    offers = [
        request(
            f"create offer {n}",
            "POST",
            "/api/offers/",
            201,
            {
                "seller_id": seller["id"],
                "product_id": product["id"],
                "simulated_price": price,
            },
            admin,
        )
        for n, (seller, price) in enumerate(zip(sellers, ["25.90", "40.00"], strict=True), 1)
    ]
    for offer in offers:
        request(
            "supply offer",
            "POST",
            f"/api/inventory/{offer['id']}/changes/",
            201,
            {
                "movement_type": "ENTRY",
                "quantity_delta": 10,
                "reason": "Fictional curl supply.",
            },
            admin,
        )
    address = {
        "recipient": "Fictional Curl Customer",
        "street": "Example Street",
        "number": "10",
        "district": "Example District",
        "city": "Example City",
        "state": "SP",
        "postal_code": "00000000",
    }
    payload = {
        "items": [
            {"offer_id": offers[0]["id"], "quantity": 2},
            {
                "offer_id": offers[1]["id"],
                "quantity": 1,
            },
        ],
        "shipping_address": address,
    }
    key = f"curl-order-{suffix}"
    order = request(
        "multi-seller purchase", "POST", "/api/orders/", 201, payload, buyer, key, "false"
    )
    canonical = {
        "items": list(reversed(payload["items"])),
        "shipping_address": {**address, "complement": "  "},
    }
    replay = request(
        "canonical keyed replay", "POST", "/api/orders/", 200, canonical, buyer, key, "true"
    )
    require(replay == order, "Canonical retry changed the order or its snapshots.")
    conflict = request(
        "key content conflict",
        "POST",
        "/api/orders/",
        409,
        {**payload, "shipping_address": {**address, "number": "11"}},
        buyer,
        key,
    )
    require(conflict["code"] == "idempotency_conflict", "The conflict code differs.")
    request("anonymous key is not authorization", "POST", "/api/orders/", 401, payload, key=key)
    request(
        "administrator cannot replay customer key", "POST", "/api/orders/", 403, payload, admin, key
    )
    request("invalid creation key", "POST", "/api/orders/", 400, payload, buyer, "invalid key")
    require(
        order["total"] == "91.80" and order["data_origin"] == "SIMULATED_API",
        "The initial simulated purchase total differs.",
    )
    request(
        "rename and reprice catalog",
        "PATCH",
        f"/api/offers/{offers[0]['id']}/",
        payload={
            "simulated_price": "30.00",
        },
        token=admin,
    )
    request(
        "rename product",
        "PATCH",
        f"/api/products/{product['id']}/",
        payload={
            "name": "Fictional Renamed Curl Lamp",
        },
        token=admin,
    )
    repriced_replay = request(
        "keyed replay after catalog edits", "POST", "/api/orders/", 200, payload, buyer, key, "true"
    )
    require(repriced_replay == order, "Catalog edits changed a keyed purchase replay.")
    original = request("purchase snapshot", "GET", f"/api/orders/{order['id']}/", token=buyer)
    require(original["total"] == "91.80", "The stored purchase total changed.")
    require(
        all(item["product_name"] == "Fictional Curl Lamp" for item in original["items"]),
        "The stored purchase name changed.",
    )
    for name in ["cancel purchase", "repeat cancellation"]:
        result = request(
            name, "POST", f"/api/orders/{order['id']}/cancel/", payload={}, token=buyer
        )
        require(result["order"]["status"] == "CANCELLED", "Cancellation did not persist.")
    cancelled_replay = request(
        "keyed replay after cancellation", "POST", "/api/orders/", 200, payload, buyer, key, "true"
    )
    require(
        cancelled_replay["id"] == order["id"] and cancelled_replay["status"] == "CANCELLED",
        "Replay reopened or replaced a cancelled order.",
    )
    for offer in offers:
        balance = request("restored stock", "GET", f"/api/inventory/{offer['id']}/", token=admin)
        require(balance["available_quantity"] == 10, "Cancellation restored an incorrect balance.")
    request("foreign order isolation", "GET", f"/api/orders/{foreign_id}/", 404, token=buyer)
    processed = request("second purchase", "POST", "/api/orders/", 201, payload, buyer)
    require(processed["total"] == "100.00", "The new-price purchase total differs.")
    payment = request(
        "simulated approval",
        "POST",
        f"/api/orders/{processed['id']}/simulated-payment/",
        payload={},
        token=admin,
    )
    repeated = request(
        "repeat approval",
        "POST",
        f"/api/orders/{processed['id']}/simulated-payment/",
        payload={},
        token=admin,
    )
    require(
        payment["simulated_payment"]["reference"] == repeated["simulated_payment"]["reference"],
        "Simulated approval repetition changed its reference.",
    )
    request(
        "paid cancellation denied", "POST", f"/api/orders/{processed['id']}/cancel/", 409, {}, buyer
    )
    request(
        "simulated shipping",
        "POST",
        f"/api/orders/{processed['id']}/ship/",
        payload={"tracking_code": f"SIMULATED-CURL-{suffix}"},
        token=admin,
    )
    delivered = request(
        "simulated delivery",
        "POST",
        f"/api/orders/{processed['id']}/deliver/",
        payload={},
        token=admin,
    )
    require(delivered["order"]["status"] == "DELIVERED", "Delivery did not persist.")
    failed_payload = {
        **payload,
        "items": [
            {"offer_id": offers[0]["id"], "quantity": 1},
            {"offer_id": offers[1]["id"], "quantity": 9999},
        ],
    }
    before = request("orders before failed purchase", "GET", "/api/orders/", token=buyer)["count"]
    failed_key = f"curl-failed-{suffix}"
    request(
        "insufficient stock rollback",
        "POST",
        "/api/orders/",
        409,
        failed_payload,
        buyer,
        failed_key,
    )
    after = request("orders after failed purchase", "GET", "/api/orders/", token=buyer)
    require(after["count"] == before, "A failed purchase left an order behind.")
    for offer, expected in zip(offers, [8, 9], strict=True):
        balance = request(
            "stock after rollback", "GET", f"/api/inventory/{offer['id']}/", token=admin
        )
        require(balance["available_quantity"] == expected, "A failed purchase changed stock.")
    movements = request(
        "movement history", "GET", f"/api/inventory/movements/?order_id={order['id']}", token=admin
    )
    require(movements["count"] == 4, "The cancellation movement count differs.")
    require(
        sum(Decimal(row["quantity_delta"]) for row in movements["results"]) == 0,
        "The cancellation ledger does not balance.",
    )
    recovered = request(
        "uncommitted key accepts corrected content",
        "POST",
        "/api/orders/",
        201,
        payload,
        buyer,
        failed_key,
        "false",
    )
    require(recovered["id"] != processed["id"], "A rolled-back key reused another order.")
    request(
        "cancel recovered purchase",
        "POST",
        f"/api/orders/{recovered['id']}/cancel/",
        payload={},
        token=buyer,
    )
    for offer, expected in zip(offers, [8, 9], strict=True):
        balance = request(
            "stock after recovered cancellation",
            "GET",
            f"/api/inventory/{offer['id']}/",
            token=admin,
        )
        require(balance["available_quantity"] == expected, "Recovery changed final stock.")
    require(
        not {"idempotency_key_hash", "request_fingerprint"}.intersection(order),
        "Internal key hashes leaked in the order response.",
    )
    request(
        "source-free report refusal", "GET", "/api/olist/reports/monthly_sales/", 409, token=admin
    )
    schema = request("authenticated OpenAPI", "GET", "/api/schema/?format=json", token=admin)
    require(schema["info"]["version"] == "1.2.0", "The API schema version differs.")
    report["assertions"] = {
        "multi_seller_total": order["total"],
        "new_price_total": processed["total"],
        "snapshots_preserved": True,
        "cancellation_restored_once": True,
        "repeated_payment_same_reference": True,
        "failed_order_fully_rolled_back": True,
        "owner_and_admin_boundaries": True,
        "all_events_simulated": True,
        "canonical_keyed_replay_same_order": True,
        "content_conflict_rejected": True,
        "replay_preserves_purchase_after_catalog_edits": True,
        "cancelled_replay_does_not_reserve_again": True,
        "key_does_not_bypass_authorization": True,
        "uncommitted_key_reusable_after_failure": True,
        "unkeyed_creation_has_no_replay_header": True,
        "internal_hashes_not_exposed": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="olist-demo")
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-demo-writes", action="store_true")
    args = parser.parse_args()
    if not args.allow_demo_writes or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", args.project):
        parser.error("Explicitly allow fictional writes and use a valid isolated Compose project.")
    values = configuration(args.env_file)
    compose = ["docker", "compose", "-p", args.project, "--env-file", str(args.env_file.resolve())]
    if args.output.exists():
        raise FileExistsError("Choose a new evidence filename before executing demo writes.")
    base_url = confirmed_url(compose)
    report = {
        "started_at_utc": datetime.now(UTC).isoformat(),
        "passed": False,
        "python_optimized": not __debug__,
        "project": args.project,
        "database": "olist_demo",
        "base_url": base_url,
        "transport_command": CURL,
        "requests": [],
        "credential_handling": (
            "Private curl config on stdin; no tokens/passwords in argv or evidence."
        ),
        "data_origin": "SIMULATED_API",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        try:
            workflow(base_url, values, report)
            report["passed"] = True
        except Exception:
            report["failure"] = "A curl workflow failed; inspect local demo state before retrying."
            raise RuntimeError(report["failure"]) from None
        finally:
            report["finished_at_utc"] = datetime.now(UTC).isoformat()
            json.dump(report, output, indent=2)
            output.write("\n")
    print(
        f"Passed {len(report['requests'])} real curl requests; credentials omitted from evidence."
    )


if __name__ == "__main__":
    main()
