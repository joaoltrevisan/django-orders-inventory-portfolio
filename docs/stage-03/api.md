# Stage 3: authentication, catalog, and historical API

> Stage delivery record. Current setup and feature scope are in the [execution guide](../getting-started.md) and [API reference](../api.md). Commands/results below retain their original stage context.

Base URL for local execution: `http://127.0.0.1:18020`. Run `docker compose up -d --wait app` after rebuilding/migrating. All examples below use JSON and English responses. Accounts and operational catalog objects are explicitly simulated, with no historical customer-to-login association.

## Routes and permissions

| Route | Methods | Access and behavior |
| --- | --- | --- |
| `/health/` | GET | Public database probe; current response `{"status":"ok","stage":3}` |
| `/api/auth/register/` | POST | Public; atomically creates a hashed-password customer account/profile; rejects role/identity overrides |
| `/api/auth/login/` | POST | Public; email/password to access and refresh JWTs |
| `/api/auth/refresh/` | POST | Public token endpoint; validates refresh signature/type/expiry and current user/password state |
| `/api/auth/me/` | GET, PATCH | Authenticated user only; writable name/phone; email/identity/privileges are protected |
| `/api/customers/` | GET | Administrator; paginated operational customer profiles |
| `/api/customers/{id}/` | GET, PATCH | Administrator; name, phone, active state; path ID is Customer PK, response also exposes separate `user_id` |
| `/api/products/`, `/api/sellers/`, `/api/offers/` | GET, POST | Authenticated reads; administrator creates; collections paginated |
| Same catalog paths with `/{id}/` | GET, PATCH | Authenticated reads; administrator updates; DELETE/PUT unsupported |
| `/api/olist/{resource}/` and `/{source_key}/` | GET | Active administrators only, even for users knowing a source ID; completed historical snapshots only |
| `/api/schema/` | GET | Administrator; generated OpenAPI for current implementation |

Historical resources are `customers`, `categories`, `products`, `sellers`, `orders`, `items`, and `payments`. Main resources use source identifiers for detail lookup; categories use source category names. Item/payment detail paths use application numeric IDs; their natural identities remain `(order, source_order_item_id)` and `(order, payment_sequential)`. Item/payment lists accept `?order_id={source_order_id}`. Every list uses stable ordering and pages of 20; follow `next`. Historical writes return 405 for authorized administrators; customers are denied before lookup.

Operational representations expose `SIMULATED_API`; historical representations expose `OLIST_HISTORICAL`. Payment rows additionally expose `payment_record_kind=HISTORICAL_RECORD`. Source timestamps are serialized as timezone-free `YYYY-MM-DD HH:MM:SS`, never with an invented `Z`. `customer_id` source joins and `customer_unique_id` repeat identity are distinct. Catalog prices are named `simulated_price`; historical product metadata has no current price or fabricated commercial name.

Inactive sellers/products/offers remain visible to administrators and are hidden from customer catalog reads. Offers initialize exactly one zero stock balance atomically. Price is a positive decimal string. Offer parents and existing product SKUs cannot be reassigned through these services. Product names, seller labels, activation, and simulated prices can change. Direct service calls recheck current account/administrator state. Stock changes, orders, payments and transitions remain Stage 4 work.

## Authentication

The JWT issuer and audience are `marketplace-operations-api`. Access expires in **5 minutes**; refresh expires in **1 day**, without rotation or lifetime extension. Both access and refresh reject inactive/deleted accounts, malformed user IDs and tokens issued before the current password hash. An existing token does not retain removed staff privileges: authorization uses the current user. No logout blacklist, password-reset endpoint or account-deletion endpoint is supplied yet. Keep tokens out of source control and logs.

Registration/login/refresh throttles are respectively 5/10/20 requests per minute. They use the local Django process cache and are not a distributed abuse-control system. Responses from account/catalog/history views use `Cache-Control: no-store`. Automated functional tests disable throttling for deterministic isolation; distributed throttling/load behavior is not claimed as tested. The server remains local development infrastructure, not public hosting.

Create your own fictional administrator interactively; no shared/default password is shipped:

```bash
docker compose run --rm migrate createsuperuser
```

Use an `example.com` email and a strong password. The executed demonstration used `admin@example.com` and `customer@example.com` with privately generated distinct passwords. Their values and JWTs are not published. A bootstrap administrator is created with owner credentials; normal HTTP requests use the restricted API database login.

## curl workflows

Use your own passwords/tokens in private local files or environment variables. The sample files below are placeholders to create locally; `.local/` is ignored. Avoid committing real credentials or putting them in shared shell history.

```json
{"email":"customer@example.com","name":"Fictional Customer","password":"YOUR_PRIVATE_STRONG_PASSWORD"}
```

Save that as `.local/customer-registration.json`. Save an email/password login object as `.local/customer-login.json`, and the administrator's separate login object as `.local/admin-login.json`.

```bash
curl --fail-with-body -sS http://127.0.0.1:18020/api/auth/register/ \
  -H 'Content-Type: application/json' --data-binary @.local/customer-registration.json
curl --fail-with-body -sS http://127.0.0.1:18020/api/auth/login/ \
  -H 'Content-Type: application/json' --data-binary @.local/customer-login.json
curl --fail-with-body -sS http://127.0.0.1:18020/api/auth/login/ \
  -H 'Content-Type: application/json' --data-binary @.local/admin-login.json
```

Keep each returned `access` token in a private environment variable (`CUSTOMER_ACCESS_TOKEN` or `ADMIN_ACCESS_TOKEN`). Use separate customer/admin tokens:

```bash
curl --fail-with-body -sS http://127.0.0.1:18020/api/auth/me/ \
  -H "Authorization: Bearer $CUSTOMER_ACCESS_TOKEN"
curl --fail-with-body -sS -X PATCH http://127.0.0.1:18020/api/auth/me/ \
  -H "Authorization: Bearer $CUSTOMER_ACCESS_TOKEN" \
  -H 'Content-Type: application/json' --data '{"name":"Updated Fictional Customer","phone":"555-0100"}'
curl --fail-with-body -sS http://127.0.0.1:18020/api/olist/orders/ \
  -H "Authorization: Bearer $ADMIN_ACCESS_TOKEN"
curl --fail-with-body -sS http://127.0.0.1:18020/api/olist/orders/00010242fe8c5a6d1ba2dd792cb16214/ \
  -H "Authorization: Bearer $ADMIN_ACCESS_TOKEN"
curl --fail-with-body -sS 'http://127.0.0.1:18020/api/olist/payments/?order_id=00010242fe8c5a6d1ba2dd792cb16214' \
  -H "Authorization: Bearer $ADMIN_ACCESS_TOKEN"
```

That source order ID was actually retrieved during HTTP verification: source status `delivered`, purchase clock `2017-09-13 08:59:02`, first line price `58.90`, freight `13.29`, and one payment row. Its `customer_id` is `3ce436f183e68e07877b285a838db11a`; repeat identity is `871766c5855e863f6eccc05f988b23cb`. These anonymized source keys grant no login or ownership rights. A customer token on the historical order collection returns 403. Administrator PATCH on that historical order returns 405.

Create separate simulated catalog records; use returned IDs instead of assuming IDs from another environment:

```bash
curl --fail-with-body -sS http://127.0.0.1:18020/api/products/ \
  -H "Authorization: Bearer $ADMIN_ACCESS_TOKEN" -H 'Content-Type: application/json' \
  --data '{"sku":"DEMO-STAGE3-002","name":"Simulated Desktop Lamp"}'
curl --fail-with-body -sS http://127.0.0.1:18020/api/sellers/ \
  -H "Authorization: Bearer $ADMIN_ACCESS_TOKEN" -H 'Content-Type: application/json' \
  --data '{"label":"Simulated Seller"}'
curl --fail-with-body -sS http://127.0.0.1:18020/api/offers/ \
  -H "Authorization: Bearer $ADMIN_ACCESS_TOKEN" -H 'Content-Type: application/json' \
  --data '{"seller_id":1,"product_id":1,"simulated_price":"25.90"}'
```

Replace the final payload's IDs with your returned values. The executed demonstration used SKU `DEMO-STAGE3-001`, IDs 1/1, and returned a simulated offer with quantity 0. Repeating a SKU or seller/product offer returns 400; examples create records and are not idempotent seed commands. Use fresh identities for another run. A repeatable operational fixture generator remains Stage 5 work.

Refresh uses a private `{"refresh":"YOUR_REFRESH_TOKEN"}` JSON file and POST `/api/auth/refresh/`; a successful response contains only a new access token. Complete schema: [validated OpenAPI JSON](../../reports/stage-03/openapi.json). The [HTTP artifact](../../reports/stage-03/http.json) records actual statuses and a small historical example; these curl forms illustrate the same endpoints and were not separately all executed as shell commands.
