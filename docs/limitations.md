# Security boundaries, limitations and next improvements

This repository demonstrates a complete scoped backend and evidence workflow. The provided Compose application uses Django's development server on loopback; it has not been deployed or validated as a publicly hosted production service.

## Implemented security

Django hashes passwords and validates them during registration. Public registration creates active nonstaff customers only; administrators are provisioned deliberately. JWT uses signed HS256 access tokens lasting five minutes and refresh tokens lasting one day, fixed audience/issuer, no refresh rotation and no token blacklist/logout endpoint. Access and refresh recheck current account activity and password-derived revocation; permissions read current staff state. Changing passwords or deactivating an account invalidates its tokens; this does not cancel work already authorized and in flight.

Customers access only their own profile and operational orders. Foreign-owned orders return 404. Administrators manage catalog, customer activity, inventory and processing, and alone read historical source data/reports. There is no claim-by-historical-ID flow. Collection endpoints paginate at 20. ORM/fixed parameterized SQL avoid interpolating user values; unknown fields and inappropriate monetary/identity/status writes are rejected. Business/database failures have English sanitized responses. API responses use `Cache-Control: no-store`.

Private configuration is generated once, ignored and mode 0600; `.env.example` contains placeholders. Never commit real identities, credentials, tokens, source archives or full issue payloads. Application/import/migration/test roles are separated; the database port is not published. The web container runs nonroot with a read-only filesystem and temporary `/tmp`. Historical facts are read-only to the API role. Owner/bootstrap access remains privileged; source fingerprints detect inconsistency against stored import metadata but are not a cryptographic trust anchor against an owner changing both facts and metadata.

Login/registration/refresh throttles use Django's per-process local-memory cache in this development setup. They are not a distributed abuse-control system. Browser cookie/session authentication is not configured; Bearer credentials belong in the Authorization header, not URLs. HTTPS termination, deployment secrets, shared rate limiting, monitoring, backups/recovery, stricter network/host configuration and operational rotation require deployment-specific work.

## Scope and evidence limits

- Historical Olist data is one immutable accepted snapshot per database, with offset-free source clocks, preserved anomalies and missing facts. Reviews and raw geolocation are fingerprinted but not imported. No real identities, current stock, catalog prices, logins, settlement/refunds or item-level seller delivery events can be inferred from it.
- Operational prices, offers, inventory, accounts, payments and fulfillment are explicitly simulated. There are no real payment, warehouse, carrier or Olist internal-system calls, separate seller suborders, partial cancellation, refunds/returns, taxes/discounts/shipping charges or multi-currency support.
- Only pending orders cancel. New deduct-on-create reservations have a 30-minute payment deadline and expire only when the explicit administrative command commits. An optional periodic worker is available through an explicitly enabled Compose overlay; default startup leaves it disabled. Delayed/stopped execution keeps units deducted. Legacy NULL deadlines remain unexpired. Optional customer-scoped creation keys support retries from the first keyed attempt; unkeyed ambiguous commits still require checking state before retrying. Keys persist indefinitely with orders, errors are not cached, replay returns current state and the guarantee does not extend to external services. Parent locks favor a clear common hierarchy over maximum concurrency.
- Cross-table totals, immutable snapshots, permitted transitions and ledger reconciliation rely on the application services. Database constraints enforce local keys/ranges/row consistency; privileged SQL can bypass service invariants. Audit history is not a tamper-proof accounting ledger.
- Reports use bounded source intervals, stable offset pagination and synchronous count/execution. They are not a materialized analytics warehouse or streaming/current-sales dashboard. Large offsets, concurrent operational load and production traffic were not benchmarked.
- Sales uses final snapshot `delivered` status and observed item value, not historical as-of status, audited revenue or settled cash. Payment facts lack per-payment event times. Repeat behavior is observed only within the stated source/window. Seller delivery is an order association, not independently measured seller shipment performance.
- The index experiment is one fixed warm-cache query on the full imported snapshot in aarch64 Docker. Its temporary index was removed. No cold-cache, production, write-load, global API speedup or adopted-index claim follows. Full result hashes for large reports cannot be regenerated from the published first-10 samples alone; rerun the collection on the locked source.
- Automated tests and independent review exercise important paths/schedules, not every possible failure. Mermaid source is provided for GitHub rendering; a rendered-diagram screenshot/export was not verified in this delivery.

## Prioritized follow-up work

1. Add deployment-specific supervision, retained log monitoring/alerts and recovery drills around the optional periodic worker. Its JSON backlog observations are not health certification; stopped/failed workers and persistent corrupt oldest rows need operator intervention. Queue fairness, quarantine and production scheduling guarantees are not implemented.
2. Design payment/refund and seller-fulfillment integrations with explicit provider/event contracts; keep imported source facts immutable.
3. Evaluate actual production report/page workloads and storage/write costs before adopting any measured index through a reviewed migration.
4. Add deployment configuration, TLS, shared throttling, observability, backup/restore drills and key rotation for a real hosting target.
5. Extend source modeling to reviews/geolocation only after new key/cardinality/privacy validation; add multiple snapshots only with explicit cross-snapshot integrity rules.

These are future changes, not implied completed functionality. Data use remains subject to [source attribution and CC BY-NC-SA 4.0](../THIRD_PARTY_DATA.md); the project makes no employment, partnership, endorsement or internal-access claim.
