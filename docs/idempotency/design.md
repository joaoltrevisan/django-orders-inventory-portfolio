# Idempotent operational order creation

## Assessment and scope

Starting point: clean commit `a761a9c`, completed six-stage service and verified PostgreSQL CI. The existing `create_order` service already validates current customers, snapshots prices/names, reserves multiple offers atomically and follows a shared parent/offer/stock lock order. Cancellation and processing already have their own consistent repetition rules. Creation currently has no key, so a client retry after an ambiguous commit can create another order.

Reuse those services, serializer boundaries, database roles, fixtures and controlled separate-connection concurrency harness. This delivery adds an optional creation key; it does not implement reservation expiry, payment-provider exactly-once delivery, suborders or historical-source mutations.

## Complete request and response contract

- `POST /api/orders/` accepts an optional `Idempotency-Key` header: 1–128 ASCII letters/digits or `.`, `_`, `:`, `-`. The value is case-sensitive, untrimmed and opaque. Empty, oversized, whitespace, comma/multiple-value or non-ASCII values return 400 before writes. It is not an authentication credential.
- Keys are scoped to the current active nonstaff Customer profile. Another customer may use the same value independently and cannot retrieve the first customer's order. Current authorization is required for both initial creation and replay; knowing a key never grants access.
- Canonical content is the validated offer IDs/quantities sorted by offer ID, plus validated/trimmed address fields with absent complement normalized to an empty string. JSON property order and offer-line order do not distinguish otherwise equivalent requests. Currency, customer, status, client prices/totals and unknown fields remain forbidden. The fingerprint format is versioned internally.
- First committed creation returns 201 and `Idempotency-Replayed: false`. Same customer/key/canonical content returns 200 and `Idempotency-Replayed: true`, with the existing order and its immutable purchase snapshots. A committed key reused with different valid content returns 409 `idempotency_conflict` without stock/order writes.
- Replay returns the current coherent order state under an order lock, not a cached byte-for-byte original response. A later cancellation/payment/shipment/delivery may therefore change its status/timestamps. Catalog repricing, renaming or deactivation does not invalidate a successful replay or recalculate its purchase prices. Replay never reserves stock again or reopens a cancelled order.
- Successful keys are retained with their order indefinitely; there is no expiry or key reuse after cancellation. Only a committed successful order consumes the key. Validation, insufficient stock or database failure rolls back the order, items, movements and key together; a later attempt may reuse that unconsumed key. Errors are not cached.
- Without a key, the existing creation behavior remains: each successful request creates a new order and receives 201. Clients requiring safe retry must provide the same key and content on every retry. The guarantee covers this database transaction, not arbitrary downstream services.

## Model, transactions and locks

Add nullable `idempotency_key_hash` and `request_fingerprint` fields to `orders_order`. Both are lowercase SHA-256 hex strings when present, otherwise both NULL. A database CHECK enforces the pair/format, and a partial unique constraint enforces `(customer_id, idempotency_key_hash)` for keyed orders. Existing rows keep NULL fields and remain valid. Raw header values and canonical payload copies are not persisted in a separate table.

Before offer locks or inserting a keyed order, obtain a PostgreSQL transaction-scoped advisory lock derived from the customer identity and key hash. This serializes requests for a key even before an order row exists. Check for an existing scoped order with `SELECT FOR UPDATE`; reject content conflicts or inspect its order/ledger/payment/shipment history and return its snapshots. New creation continues through the existing atomic reservation service. Recheck current customer authorization after waiting for the advisory lock.

Hierarchy becomes **optional creation-key advisory lock → existing order when replaying → sellers by ID → products by ID → offers by ID → stock by offer ID**. Replay does not acquire catalog/stock locks; lifecycle services never acquire creation-key locks. The unique index remains a second line of database integrity. A collision in the 64-bit advisory-lock identifier only adds serialization: exact customer/key-hash lookup determines replay identity. Full SHA-256 key/content identity relies on the normal cryptographic collision assumption.

Use bound SQL for the lock and retain READ COMMITTED. The lock lasts until the enclosing transaction ends, including an outer caller's transaction; no session lock or manual release is needed. See [PostgreSQL advisory locks](https://www.postgresql.org/docs/17/explicit-locking.html#ADVISORY-LOCKS), [lock functions](https://www.postgresql.org/docs/17/functions-admin.html#FUNCTIONS-ADVISORY-LOCKS) and [Django constraints](https://docs.djangoproject.com/en/5.2/ref/models/constraints/). This is application-managed serialization, not a database trigger that makes privileged raw SQL obey every service invariant.

## Required verification before handoff

Exercise missing/invalid keys, unchanged unkeyed behavior, canonical equivalence, payload conflicts, cross-customer isolation and revoked roles, changed/deactivated catalog, replay after cancellation/processing, full rollback and database pair/unique constraints. Coordinate separate PostgreSQL connections to observe same-key waiting, conflicting-payload contention, first-attempt rollback and coherent replay while cancellation holds the order lock. Preserve actual observed blocking evidence, not arbitrary-delay claims.

Generate an additive migration and SQL export, verify existing-row compatibility and restoration, update OpenAPI/API examples/current diagrams and limitations, run the complete suite and actual HTTP checks, then independent review and hosted CI. Earlier stage evidence remains dated rather than rewritten. New operational hash fields do not enter historical import fingerprints, SQL metrics or benchmark data.
