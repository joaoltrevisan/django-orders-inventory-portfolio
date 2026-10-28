# API reference and curl workflows

Base URL for the isolated seeded demo is `http://127.0.0.1:18022`; the existing primary service uses port 18020. All routes end in `/`. Bodies are JSON, identifiers are integers unless explicitly historical source keys, money is decimal BRL, and collection page size is 20. The [OpenAPI document for API 1.3.0](../reports/worker/local/openapi.json) is the current machine-readable contract; `GET /api/schema/` requires an administrator token. This is the API's version label, not a production readiness claim.

## Authentication and permissions

| Route | Methods | Access / contract |
| --- | --- | --- |
| `/health/` | GET | Public database liveness probe; 200 or 503 |
| `/api/auth/register/` | POST | Public; email, name, password, optional phone; creates customer, never administrator; 201 |
| `/api/auth/login/` | POST | Public email/password; returns access and refresh JWTs |
| `/api/auth/refresh/` | POST | Public token exchange; valid refresh plus current active account/password required; returns new access only |
| `/api/auth/me/` | GET, PATCH | Authenticated self; PATCH name/phone only |
| `/api/customers/`, `/api/customers/{id}/` | GET | Administrator; ID is Customer profile PK, distinct from User PK |
| `/api/customers/{id}/` | PATCH | Administrator; name, phone, is_active; no password/staff/identity changes |
| `/api/products/`, `/api/sellers/`, `/api/offers/` | GET, POST | Authenticated reads; administrator creates; offers start with stock 0 |
| `/api/products/{id}/`, `/api/sellers/{id}/`, `/api/offers/{id}/` | GET, PATCH | Authenticated reads; administrator edits/deactivates; SKU and offer parents immutable |
| `/api/orders/` | GET, POST | Own customer orders / all admin-visible orders; POST active nonstaff customer only |
| `/api/orders/{order_id}/` | GET | Owner or administrator; foreign-owned IDs return 404 |
| `/api/orders/{order_id}/cancel/` | POST | Owner or administrator; pending only, release once |
| `/api/orders/{order_id}/simulated-payment/` | POST | Administrator; simulated approval before reservation deadline, no real charge |
| `/api/orders/{order_id}/ship/`, `/api/orders/{order_id}/deliver/` | POST | Administrator; permitted whole-order processing |
| `/api/inventory/`, `/api/inventory/{offer_id}/` | GET | Administrator; balance identity is offer ID |
| `/api/inventory/{offer_id}/changes/` | POST | Administrator; ENTRY or signed ADJUSTMENT with reason |
| `/api/inventory/movements/` | GET | Administrator; append-only movement history through the API |
| `/api/olist/{resource}/`, `/api/olist/{resource}/{key}/` | GET | Administrator historical reads; resources customers/categories/products/sellers/orders/items/payments |
| `/api/olist/reports/{report_name}/` | GET | Administrator; completed source required; paginated fixed SQL report |

Customers see only active products/sellers and offers whose seller/product/offer are active. Historical customer/product/seller/order detail keys are exact source strings; category detail key is source category name; item/payment detail keys are surrogate PKs. Historical item/payment lists support `?order_id=<32 lowercase hex source order ID>`. No customer can claim historical ownership. Hard deletion, direct order edits and historical POST/PATCH/DELETE are unavailable.

Operational order lists support exact lifecycle `status` and administrator-only `customer_id` (Customer profile PK). Movement lists accept optional `offer_id` and operational `order_id`; both are positive bigint identities, 1–9223372036854775807. These filters are combined when supplied together. Source `order_id` filters are 32-character lowercase hexadecimal identifiers and belong to a different namespace. All collections accept `page`; invalid values or inaccessible/out-of-range results follow the documented validation/404 rules.

Access JWT lifetime is **5 minutes**; refresh lifetime **1 day**. HS256 signature, issuer/audience, token type/expiry, current active account and password-derived revocation are checked. Staff changes affect existing tokens' permissions. Refresh rotation, blacklist and logout/revoke endpoints are not implemented. Login/register/refresh limits are 10/5/20 per minute using a per-process cache in this local setup. Use headers, never token query parameters. See [security limits](limitations.md).

## Private login payload and token files

The following examples make writes when executed. Use the [isolated setup](getting-started.md), not a populated service whose identities/states you have not checked. Real end-to-end curl execution is available as `scripts/verify_curl.py`; the individual forms below show how to explore those same routes manually and are not claimed as additional separate shell runs.

Prepare ignored payload files with private permissions, prompting without printing the password:

```bash
umask 077
mkdir -p .local/api
BASE_URL=http://127.0.0.1:18022
python3 - <<'PY'
import getpass, json
from pathlib import Path
payload = {"email": input("Email: "), "password": getpass.getpass("Password: ")}
with Path('.local/api/login.json').open('x') as output:
    json.dump(payload, output)
PY
curl --fail-with-body -sS "$BASE_URL/api/auth/login/" \
  -H 'Content-Type: application/json' --data-binary @.local/api/login.json \
  -o .local/api/login-response.json
python3 - <<'PY'
import json
from pathlib import Path
tokens = json.loads(Path('.local/api/login-response.json').read_text())
with Path('.local/api/authorization.header').open('x') as output:
    output.write('Authorization: Bearer ' + tokens['access'] + '\n')
with Path('.local/api/refresh.json').open('x') as output:
    json.dump({'refresh': tokens['refresh']}, output)
PY
curl --fail-with-body -sS "$BASE_URL/api/auth/me/" -H @.local/api/authorization.header
curl --fail-with-body -sS "$BASE_URL/api/auth/refresh/" \
  -H 'Content-Type: application/json' --data-binary @.local/api/refresh.json \
  -o .local/api/refreshed-response.json
```

Use fresh filenames or deliberately manage private files before repeating; Python creation refuses overwrite, while curl response `-o` can replace its target. Refresh output contains a new access token; update the private header when the old one expires. For two roles, create separate files/directories and header names such as `.local/api/admin.header` and `.local/api/customer.header`. Never publish login responses or enable shell tracing. Curl header files keep tokens out of process argv; the automated runner instead sends private config on stdin.

For registration save a private payload containing fictional `email`, `name`, strong `password`, optional `phone`, then:

```bash
curl --fail-with-body -sS "$BASE_URL/api/auth/register/" \
  -H 'Content-Type: application/json' --data-binary @.local/api/register.json
```

No default password is committed. The demo password is generated privately; public registration cannot grant administrative access.

## Catalog, supply and purchase

Administrator examples create a product, seller and offer. Substitute each returned ID; IDs below illustrate shape only. SKU accepts uppercase letters/digits with `.`, `_`, `-`, up to 64 characters. Monetary inputs use exact strings; current offer prices are simulated.

```bash
curl --fail-with-body -sS "$BASE_URL/api/products/" -H @.local/api/admin.header \
  -H 'Content-Type: application/json' --data '{"sku":"EXAMPLE-LAMP-001","name":"Fictional Lamp"}'
curl --fail-with-body -sS "$BASE_URL/api/sellers/" -H @.local/api/admin.header \
  -H 'Content-Type: application/json' --data '{"label":"Fictional Seller"}'
curl --fail-with-body -sS "$BASE_URL/api/offers/" -H @.local/api/admin.header \
  -H 'Content-Type: application/json' --data '{"seller_id":1,"product_id":1,"simulated_price":"25.90"}'
curl --fail-with-body -sS "$BASE_URL/api/inventory/1/changes/" -H @.local/api/admin.header \
  -H 'Content-Type: application/json' \
  --data '{"movement_type":"ENTRY","quantity_delta":10,"reason":"Fictional opening supply."}'
```

Create another seller/offer to demonstrate multi-seller orders. Save `.local/api/order.json` with **your returned offer IDs**:

```json
{
  "items": [{"offer_id": 1, "quantity": 2}, {"offer_id": 2, "quantity": 1}],
  "shipping_address": {
    "recipient": "Fictional Customer", "street": "Example Street", "number": "10",
    "district": "Example District", "city": "Example City", "state": "SP", "postal_code": "00000000"
  }
}
```

```bash
curl --fail-with-body -sS "$BASE_URL/api/orders/" -H @.local/api/customer.header \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: purchase-example-001' \
  --data-binary @.local/api/order.json
curl --fail-with-body -sS "$BASE_URL/api/orders/?status=PENDING_PAYMENT&page=1" \
  -H @.local/api/customer.header
curl --fail-with-body -sS "$BASE_URL/api/orders/1/" -H @.local/api/customer.header
```

Use the returned order ID for later requests. Accept 1–100 distinct offers, integer JSON quantities 1–9999 and a structured fictional Brazilian address. Duplicate offers, client prices/totals/customer/status/timestamps are rejected. The server snapshots price/name/SKU/seller, calculates decimal totals and atomically deducts all offers. At prices 25.90 and 40.00, quantities 2/1 total **91.80**; the actually executed curl workflow verified that total, old snapshots after edits and a new-price purchase total of **100.00**.

## Creation keys and safe retry

For a purchase that may be retried, send an `Idempotency-Key` on the first request and keep the same key and validated content on retries. The example above uses `purchase-example-001`; choose a fresh value for each intended purchase. To inspect the response status/headers, add curl `--include`.

| Request | Result |
| --- | --- |
| First successful keyed creation | 201, `Idempotency-Replayed: false` |
| Same customer/key/normalized content | 200, `Idempotency-Replayed: true`, same order ID |
| Committed key with different valid content | 409, `code: idempotency_conflict` |
| Invalid key or request body | 400; no order/key consumed |
| No key | Each successful call creates a distinct order, 201, no replay header |

The key is case-sensitive and must contain 1–128 ASCII letters/digits or `.`, `_`, `:`, `-`; whitespace, empty values, commas and non-ASCII characters are rejected. Scope is the current active nonstaff Customer profile. Knowing a key grants no access. IDs/quantities are validated and item lines sorted; address text is trimmed and an absent complement equals an empty complement. JSON property order and item-line order do not change identity. Prices/totals remain server-owned.

Replay returns the current coherent stored order state, not cached original response bytes. It preserves purchase snapshots after catalog edits and returns `CANCELLED` after cancellation without reserving again. Successful keys are retained with their order indefinitely, including after cancellation. Validation, insufficient stock and transaction failures consume no key; errors are not cached and a corrected attempt may reuse an uncommitted key. Only SHA-256 identity/content hashes are stored, hidden from API responses. The guarantee covers this database transaction, not external payment processing. See the [full contract and lock design](idempotency/design.md).

Without a key, investigate an ambiguous commit before retrying. A key cannot be attached retroactively to an existing unkeyed purchase. Reservation deadlines are described below; replay never extends them.

## Cancel or process another order

Cancel a pending order with its owner/admin token:

```bash
curl --fail-with-body -sS -X POST "$BASE_URL/api/orders/1/cancel/" \
  -H @.local/api/customer.header -H 'Content-Type: application/json' --data '{}'
```

Consistent repetition returns the original cancellation without another release/time change. Only pending orders cancel. For a **different pending order before its deadline**, an administrator can execute:

```bash
curl --fail-with-body -sS -X POST "$BASE_URL/api/orders/2/simulated-payment/" \
  -H @.local/api/admin.header -H 'Content-Type: application/json' --data '{}'
curl --fail-with-body -sS -X POST "$BASE_URL/api/orders/2/ship/" \
  -H @.local/api/admin.header -H 'Content-Type: application/json' \
  --data '{"tracking_code":"SIMULATED-EXAMPLE-001"}'
curl --fail-with-body -sS -X POST "$BASE_URL/api/orders/2/deliver/" \
  -H @.local/api/admin.header -H 'Content-Type: application/json' --data '{}'
curl --fail-with-body -sS "$BASE_URL/api/inventory/movements/?order_id=2" \
  -H @.local/api/admin.header
```

All these order IDs are placeholders to replace, not a script against the preexisting seeded order states. Repeated simulated approval returns the existing reference; shipping repetitions require matching tracking data; delivery repetition preserves the original timestamp. Invalid skips/reversals and paid-order cancellation return 409. Action responses contain `order`, nullable `simulated_payment` and nullable `shipment`; source payments are never processed by these routes. Exact operational rules and lock hierarchy are in [architecture](architecture.md).

## Reservation deadlines and explicit expiry

New operational orders have read-only `reservation_expires_at = created_at + 30 minutes` and nullable `expired_at`. Existing orders retain NULL deadlines and remain payable under the earlier rules. The 30-minute duration is this demonstration's policy, not a fact inferred from Olist data. Historical routes/statuses are unaffected.

For pending orders with a deadline, simulated payment is permitted only when PostgreSQL wall time read after the order lock is strictly earlier. At or after the boundary, return 409 `reservation_expired` without payment, status change or stock release. A payment accepted before the boundary may commit later. Once paid, normal shipping/delivery remains possible after the original deadline.

Overdue orders remain `PENDING_PAYMENT` with stock deducted until cancellation or the explicit administrator command below commits. Owner/admin cancellation still works while pending, including overdue reservations. `EXPIRED` is terminal; cancellation/payment/shipping/delivery reject it. GET and keyed replay return persisted state/deadline without side effects or extension.

Run the command using the correct existing project/env and API database role, with an active staff actor. Example for an intentionally configured isolated demo:

```bash
docker compose -p olist-demo --env-file .local/analysis/demo.env run --rm app \
  expire_reservations --expected-database olist_demo \
  --actor-email admin@example.com --limit 100
```

An [optional periodic worker](worker/operations.md) can invoke this service; default startup leaves it disabled. The command uses one transaction per attempted order and skips locked rows. It restores every item quantity once through positive RELEASE movements, attributed to the named administrator, and writes `EXPIRED`/`expired_at`. Its JSON includes cutoff, limit, attempted/expired/selected-skipped IDs and sanitized failures. Locked-row skips are not enumerated; an empty report does not prove no due work remains. Attempts are bounded to 1–1000; query scan/wait time is not bounded by that count. Failures return a nonzero exit while retaining earlier committed successes; inspect the report before rerunning. Legacy NULL-deadline, paid and other terminal orders are not selected. [Rules and recovery](reservations/design.md) explain authority rechecks, cutoff and rollback.

## Historical reads and reports

Run these against an environment deliberately containing the accepted source and a fictional administrator account, such as the existing primary service, with that environment's header. A source-free demo has no historical records. Source customers are not login accounts.

```bash
curl --fail-with-body -sS 'http://127.0.0.1:18020/api/olist/orders/?page=1' \
  -H @.local/api/admin.header
curl --fail-with-body -sS \
  'http://127.0.0.1:18020/api/olist/reports/monthly_sales/?start=2017-01-01%2000:00:00&end=2018-01-01%2000:00:00&page=1' \
  -H @.local/api/admin.header
```

Never reuse a token signed with another environment's secret. Historical detail identifiers, filters and source-value meanings are in the [dictionary](olist/data-dictionary.md). The [SQL portfolio](stage-05/sql-portfolio.md) lists all 12 allowed report names and their exact grains/status/null rules. Report parameters: timezone-free `start` inclusive / `end` exclusive in `YYYY-MM-DD HH:MM:SS`; increasing interval up to ten years; defaults 2016-09-01 through 2018-11-01. `min_units` defaults 10 (1–1000000), `min_orders` defaults 2 (2–1000000), `page` starts at 1. Not every threshold affects every query.

Reports return `{count, next, previous, results, data_origin, date_basis}`. Rows vary by report; money is serialized as exact decimal strings. `data_origin=OLIST_HISTORICAL`; default sales uses snapshot `delivered` orders. Item and payment amounts are preaggregated separately; missing sides remain NULL/flags. Historical payment `payment_record_kind=HISTORICAL_RECORD` is distinct from operational `SIMULATED_APPROVAL_NO_REAL_CHARGE`. Source clocks have no verified timezone; operating event timestamps use aware UTC.

## Statuses and safe retries

| HTTP status | Meaning |
| --- | --- |
| 200 / 201 | Read/action/repetition / creation |
| 400 | Field/shape validation; usually field-name arrays or `non_field_errors` |
| 401 / 403 | Missing/invalid token / authenticated role forbidden |
| 404 / 405 | Missing/foreign-owned object or unknown page/report / unsupported method |
| 409 | Business conflict `{code, detail}`; insufficient stock, invalid transition, integrity/tracking/capacity conflict, unavailable complete history, committed key/content mismatch, overdue payment reservation |
| 429 | Authentication endpoint throttle |
| 500 / 503 | Sanitized database-operation failure / health database unavailable |

Business response shape is `{"code":"insufficient_stock","detail":"Insufficient stock for offer <id>."}`, with the actual offer ID in the English detail. Stable codes should drive clients. For safe creation retry, provide the same optional key and normalized content from the first attempt. Without a key, look up state and investigate an ambiguous commit before retrying. [Limitations](limitations.md) document production/security and functional boundaries.
