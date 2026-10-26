# Stage 1: initial assessment

Assessment date: 2026-10-26. Status: design delivered; technical review pending.

## Workspace inspection before file creation

The workspace contains unrelated data-science work and an existing related project named `loja-pedidos-estoque`. Inspection covered its README, architecture and domain documents, dependency pins, Docker configuration, models, migrations, authentication and permissions, order and inventory services, report selectors, benchmark runner, publication checker, and controlled-concurrency test helper. No applicable `AGENTS.md` was found in the workspace ancestry or related project file inventory.

The related project is a separate Git repository at commit `21b5b17`, dated 2026-10-24. Its working tree was clean when inspected. Its origin is [joaoltrevisan/loja-pedidos-estoque](https://github.com/joaoltrevisan/loja-pedidos-estoque), confirmed through the GitHub API as public. The authenticated account is `joaoltrevisan`.

The user requested a **new repository** and authorized incremental commits. This project therefore starts with a separate Git history and design documents. The related repository, its files, databases, running services, and history are preserved. No old source files, secrets, database volumes, benchmark outputs, or test results have been copied into the new repository.

## Reuse assessment

| Existing component | Evidence inspected | Proposed treatment in later stages |
| --- | --- | --- |
| Django domain split | `accounts`, `catalog`, `inventory`, `orders`, `reports`, `common` | Reuse the simple monolith structure after review |
| Relational models | Nine domain models with FKs, unique constraints, checks, decimal money, purchase snapshots | Reuse compatible concepts and review each migration before adoption |
| Authentication | Custom email-based user, Django password hashing, SimpleJWT, active-user checks | Adapt to English messages and verify token behavior |
| Transaction services | `transaction.atomic()`, product/stock locks ordered by product ID, order locking for transitions | Reuse the strategy; re-test rollback and contention in the new repository |
| Stock ledger | Signed movements with actor, reason, product, optional order, reservation/release uniqueness | Reuse; verify append-only API behavior and reconciliation |
| Lifecycle | Pending payment, paid, shipped, delivered, cancelled; simulated payment and shipment records | Keep this explicit lifecycle without a real payment integration |
| Tests | API, constraints, service rollback, reports, and concurrency modules | Adapt relevant cases; do not inherit a passing-test claim |
| Concurrency helper | Independent PostgreSQL connections, events, backend PIDs, `pg_blocking_pids()` | Reuse the controlled coordination approach |
| Demo and benchmark tools | `seed_demo`, isolated benchmark creation, JSON plans, repeated runs, result fingerprints | Review and adapt; keep datasets and new measurements separate |
| Docker and CI | Python/PostgreSQL image pins, app database role, non-root application container, GitHub Actions | Revalidate in Stage 2 and later CI work |

## Gaps against the current requirements

1. Existing prose documentation, significant comments/docstrings, validation messages, choice labels, and error responses are in Portuguese. New project artifacts and application-facing text must be English. This requires deliberate adaptation, including Django/DRF locale configuration, rather than a blind copy.
2. Existing account routes provide registration, login, refresh, and self-profile only. Administrative customer listing, detail, update, and deactivation must be designed and implemented.
3. Existing cancellation is owner-only. The new permission model also permits administrators to cancel pending orders. Permission checks and audit actor assertions must be updated together.
4. Existing reports are mostly ORM selectors. A standalone PostgreSQL SQL collection covering the required joins, `HAVING`, CTEs, window functions, empty-result semantics, and business explanations is missing from the inspected SQL inventory.
5. A complete schema-only SQL export consistent with migrations was not found. The only inspected `.sql` file initializes a database role. A migration-created database must be exported and restoration checked in Stage 2.
6. Existing performance JSON and reports are historical evidence. The new experiment must execute its own identical SQL before/after comparison, preserve individual samples and plans, and verify the same data and results.
7. Existing README claims 251 passing tests. Those tests were not executed in this assessment and do not establish a result for the new repository.
8. An upper stock limit needs a cancellation-headroom rule so restocking cannot make a later permitted release overflow. The proposed rule is in the requirements document and needs explicit tests.

## Stack decision and versions observed

Retain Python 3.12, Django 5.2 LTS, PostgreSQL 17, and the existing DRF-based architecture to reduce migration risk and preserve useful work. These supported release families are appropriate for the scope. No dependencies were installed or changed during Stage 1.

| Component | Actually observed during assessment | New-project status |
| --- | --- | --- |
| Host Python | 3.14.7 from `python3 --version` | Documentation verification only; not the selected app runtime |
| Related-project virtualenv Python | 3.12.15 | Candidate app pin, to reproduce in Stage 2 |
| Django | 5.2.18 installed in related virtualenv | Candidate pin |
| Django REST Framework | 3.18.3 installed in related virtualenv | Candidate pin |
| SimpleJWT | 5.5.1 installed in related virtualenv | Candidate pin; compatibility qualification below |
| PyJWT | 2.15.1 installed in related virtualenv | Candidate pin |
| psycopg | 3.3.6 installed in related virtualenv | Candidate pin |
| drf-spectacular | 0.30.0 installed in related virtualenv | Reuse for OpenAPI if verified |
| Ruff | 0.17.2 installed in related virtualenv | Candidate development pin |
| PostgreSQL | `postgres:17.11-bookworm` configured in related Compose | Configuration evidence only; server not queried in Stage 1 |
| Docker CLI | 29.9.2, build `a82e528` | Executed on host |
| Docker Compose CLI | v5.6.1 | Executed on host |

`pip check` in the related virtualenv reported `No broken requirements found.` This checks installed dependency declarations, not runtime correctness. Access to the Docker daemon was denied by the sandbox, so no running PostgreSQL version was observed. Stage 2 must record `SELECT version()`, Python/package versions inside the application container, Compose/Engine versions, and image identities actually used.

### Support and compatibility evidence

Official sources checked on the assessment date:

- [Django supported releases](https://www.djangoproject.com/download/): 5.2 is an LTS series with extended support through April 2028.
- [Django 5.2 Python compatibility](https://docs.djangoproject.com/en/5.2/releases/5.2/): Python 3.12 belongs to the supported versions.
- [Python version status](https://devguide.python.org/versions/): Python 3.12 receives security maintenance through October 2028. It is supported, although it is no longer in the bugfix phase.
- [DRF requirements](https://www.django-rest-framework.org/): Django 5.2 and Python 3.12 are supported; the [release notes](https://www.django-rest-framework.org/community/release-notes/) identify 3.18.3.
- [PostgreSQL version policy](https://www.postgresql.org/support/versioning/): PostgreSQL 17 is supported through November 2029, with 17.11 listed as its current minor release.
- [SimpleJWT 5.5.1 package metadata](https://raw.githubusercontent.com/jazzband/djangorestframework-simplejwt/v5.5.1/setup.py) includes Django 5.2. Its [tagged test matrix](https://raw.githubusercontent.com/jazzband/djangorestframework-simplejwt/v5.5.1/tox.ini) includes Python 3.12/Django 5.2 with DRF 3.15. Its [getting-started page](https://django-rest-framework-simplejwt.readthedocs.io/en/stable/getting_started.html) lists older combinations.

The SimpleJWT release matrix does **not** establish an upstream-tested DRF 3.18 combination. Package requirements allow it and the existing environment has it installed, but compatibility remains an integration check for Stage 2/3. Do not downgrade to an obsolete DRF release just to match an old matrix. Recheck maintained JWT options, published metadata, and security updates before locking the new environment; document any remaining upstream support limitation before implementing authentication.

## Changes in scope and conflict resolution

The previous project used eleven stages and owner-only cancellation. This request defines six stages and broader administrative responsibilities. The six-stage plan and the permission matrix in the new requirements document take precedence. Historic approval documents are not approvals of this new design.

Payments and shipments are useful existing concepts, but the current request does not require a payment gateway. Keep a clearly labeled **simulated approval** to explain `PENDING_PAYMENT -> PAID`, followed by shipping and delivery. Do not add card fields, real charges, refunds, or external integrations.

Publishing the repository and committing incremental work are authorized. That authorization does not remove the user's explicit technical-review checkpoint after every stage. Only Stage 1 is delivered here.
