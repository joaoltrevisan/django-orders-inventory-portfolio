# Stage 4: order and inventory workflows

This extends the [authentication/catalog guide](../stage-03/api.md) with simulated operational orders, offer inventory and lifecycle actions. Source `olist_*` data stays in its own read-only namespace. No action calls a payment provider, merchant system, warehouse, carrier, or Olist internal API.

## Run and authenticate

Preserve your existing `.env`, database and volumes. From the repository root:

```bash
docker compose build app
docker compose up -d --wait db
docker compose run --rm migrate
docker compose run --rm migrate configure_database_roles
docker compose up -d --wait app
curl --fail-with-body -sS http://127.0.0.1:18020/health/
```

Current health is `{"status":"ok","stage":4}`. No model/migration/schema change was necessary; the existing verified schema already contained the operational tables and constraints. First-time setup still needs private environment generation and an explicit Olist import as documented in earlier guides. Do not run the empty-history Stage 2 permission probe on this populated database. Docker remains a local development server, not public production hosting.

Obtain separate customer/admin Bearer JWTs using the Stage 3 guide. Store private payloads under ignored `.local/`, keep passwords/tokens out of Git and shared shell history, and use only fictional identities/addresses. All operational monetary values are decimal BRL; client-supplied prices, total, currency, customer, timestamps and arbitrary status fields are rejected.

## Endpoints

| Route | Methods | Access and effect |
| --- | --- | --- |
| `/api/orders/` | GET | Customer's own orders or all administrator-visible orders; page size 20, stable ID ordering |
| `/api/orders/` | POST | Active nonstaff customer only; atomic multi-seller creation/reservation; returns 201 |
| `/api/orders/{id}/` | GET | Owner or active administrator; foreign-owned identifiers return 404 |
| `/api/orders/{id}/cancel/` | POST `{}` | Owner or administrator; pending-only cancellation; consistent repetition returns 200 without a new release |
| `/api/orders/{id}/simulated-payment/` | POST `{}` | Administrator; pending → paid; no real charge |
| `/api/orders/{id}/ship/` | POST | Administrator; paid → shipped; optional fictional `tracking_code` |
| `/api/orders/{id}/deliver/` | POST `{}` | Administrator; shipped → delivered |
| `/api/inventory/` | GET | Administrator; paginated offer balances |
| `/api/inventory/{offer_id}/` | GET | Administrator; current simulated available quantity |
| `/api/inventory/{offer_id}/changes/` | POST | Administrator; atomic `ENTRY`/`ADJUSTMENT` and audit movement; returns 201 |
| `/api/inventory/movements/` | GET | Administrator; paginated immutable movement history, optional `offer_id`/`order_id` filters |

Order lists accept `?status=PENDING_PAYMENT` and other exact operational status values. Only administrators may filter by `customer_id`, which is the **Customer profile PK**, not User PK or a historical source key. Querysets are scoped before object lookup. Orders, items, addresses, payments, shipments, balances and movements have no direct PATCH/DELETE mutation endpoints. Catalog edits retain their separate administrative routes.

Order responses show stored product SKU/name, seller label, quantity, unit price and subtotal for each immutable offer identity. Detail responses include nullable simulated payment/shipment. Lifecycle responses wrap `order`, `simulated_payment` and `shipment`, captured under the existing order lock. Every operational representation exposes `SIMULATED_API`; payments additionally say `SIMULATED_APPROVAL_NO_REAL_CHARGE`. Historical payment records continue to say `HISTORICAL_RECORD`.

## Supply and purchase

Create your simulated product/sellers/offers using the Stage 3 catalog endpoints; each new offer starts with zero available stock. Use returned IDs, not assumed identities from another database. The executed Stage 4 demonstration used offer IDs **2 and 3** for the same simulated product from two sellers; its initial current prices were BRL 25.90 and BRL 40.00.

```bash
curl --fail-with-body -sS http://127.0.0.1:18020/api/inventory/2/changes/ \
  -H "Authorization: Bearer $ADMIN_ACCESS_TOKEN" -H 'Content-Type: application/json' \
  --data '{"movement_type":"ENTRY","quantity_delta":10,"reason":"Initial fictional supply."}'
curl --fail-with-body -sS http://127.0.0.1:18020/api/inventory/3/changes/ \
  -H "Authorization: Bearer $ADMIN_ACCESS_TOKEN" -H 'Content-Type: application/json' \
  --data '{"movement_type":"ENTRY","quantity_delta":5,"reason":"Initial fictional supply."}'
```

For purchase, save this fictional JSON as `.local/order-request.json`, substituting your own returned offer IDs:

```json
{
  "items": [{"offer_id": 2, "quantity": 2}, {"offer_id": 3, "quantity": 1}],
  "shipping_address": {
    "recipient": "Fictional Customer", "street": "Example Street", "number": "10",
    "district": "Example District", "city": "Example City", "state": "SP",
    "postal_code": "00000000"
  }
}
```

```bash
curl --fail-with-body -sS http://127.0.0.1:18020/api/orders/ \
  -H "Authorization: Bearer $CUSTOMER_ACCESS_TOKEN" -H 'Content-Type: application/json' \
  --data-binary @.local/order-request.json
curl --fail-with-body -sS http://127.0.0.1:18020/api/orders/ \
  -H "Authorization: Bearer $CUSTOMER_ACCESS_TOKEN"
curl --fail-with-body -sS http://127.0.0.1:18020/api/orders/1/ \
  -H "Authorization: Bearer $CUSTOMER_ACCESS_TOKEN"
```

The first actually executed purchase returned total **91.80**, deducted quantities 2/1 and stored the original catalog labels/prices. Later catalog renaming/repricing left that order unchanged. A second purchase used the new BRL 30.00 first-offer price and total **100.00**. These are simulated examples, not observed historical Olist prices.

## Cancel or process the whole order

Use the returned order ID. For a pending order:

```bash
curl --fail-with-body -sS -X POST http://127.0.0.1:18020/api/orders/1/cancel/ \
  -H "Authorization: Bearer $CUSTOMER_ACCESS_TOKEN" -H 'Content-Type: application/json' --data '{}'
```

Repeat the same authorized request to retrieve the same cancelled state without restoring stock again. Administrative cancellation uses the administrator token on that route; it records the actual administrator as the release actor, including when the customer's account or catalog objects are inactive.

For another pending order, the administrator can approve a simulated payment, ship and deliver:

```bash
curl --fail-with-body -sS -X POST http://127.0.0.1:18020/api/orders/2/simulated-payment/ \
  -H "Authorization: Bearer $ADMIN_ACCESS_TOKEN" -H 'Content-Type: application/json' --data '{}'
curl --fail-with-body -sS -X POST http://127.0.0.1:18020/api/orders/2/ship/ \
  -H "Authorization: Bearer $ADMIN_ACCESS_TOKEN" -H 'Content-Type: application/json' \
  --data '{"tracking_code":"SIMULATED-STAGE4-001"}'
curl --fail-with-body -sS -X POST http://127.0.0.1:18020/api/orders/2/deliver/ \
  -H "Authorization: Bearer $ADMIN_ACCESS_TOKEN" -H 'Content-Type: application/json' --data '{}'
```

Repeating payment returns the existing reference; repeating delivery preserves its timestamp. Shipping repetitions require the original tracking data. Paid orders cannot be cancelled; pending orders cannot skip payment/shipping. All actions process the **entire** multi-seller order. Separate seller suborders, partial cancellation, refunds and independent seller shipments are not implemented.

Inventory corrections use signed nonzero `ADJUSTMENT` with a mandatory reason. Negative corrections cannot reduce available stock below zero; positive corrections/entries preserve cancellation headroom. Read balances and movements with administrator GET requests. Corrections append history; they never edit previous entries.

## Errors and repeatability

Validation uses 400; missing/invalid authentication 401; forbidden roles 403; missing/foreign-owned order IDs 404. Business conflicts use 409 with stable `code` and English `detail`: `insufficient_stock`, `offer_inactive`, `offer_unavailable`, `stock_unavailable`, `stock_limit_exceeded`, `invalid_transition`, `tracking_conflict`, or `integrity_conflict`. Integrity conflicts require investigation and never silently repair records.

Unexpected database failures use sanitized 500 `database_error`; SQL text, credentials and source rows are not returned. A failure inside an active atomic operation rolls back its writes. A connection failure at commit can leave the client uncertain; check order state before retrying. Creation has no idempotency key and is not automatically retried.

These curl forms illustrate the workflows executed by the actual HTTP client in [http.json](../../reports/stage-04/http.json); they were not separately all executed as shell commands. Do not replay them assuming a pristine database: the executed demonstration already left orders 1/2/3 in cancelled/delivered/cancelled states and available quantities **8/4** on offers 2/3. Supply and purchase POSTs append new operations; use fresh fixtures/IDs for another demonstration. The repeatable fixture generator remains Stage 5 work. Current schema: [validated OpenAPI](../../reports/stage-04/openapi.json).
