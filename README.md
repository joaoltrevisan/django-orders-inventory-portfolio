# Order and Inventory Management Service for Olist

A backend service by João Trevisan designed to address order and inventory management needs in Olist's marketplace context. Built with Django REST Framework and PostgreSQL, the solution covers multi-seller orders, seller offers, inventory control, customer access, and sales analytics, with relational integrity and transactional consistency at its core.

Repository: [joaoltrevisan/django-orders-inventory-portfolio](https://github.com/joaoltrevisan/django-orders-inventory-portfolio).

## Current delivery

**Stage 4: transactional multi-seller orders, auditable offer inventory, cancellation and simulated processing.**

The service runs in its own Docker Compose environment with restricted database roles. The historical snapshot is imported and verified independently, while simulated accounts, offers, inventory and orders stay separate. Orders reserve all seller offers atomically, retain purchase snapshots, and support permitted cancellation/payment/shipping/delivery actions. The executed suite passed **106 tests**, including **15 observed PostgreSQL contention scenarios**; **47 HTTP requests** verified the current workflow, and strict OpenAPI validation passed for **37 paths**. The SQL business portfolio and measured index experiment remain Stage 5 work.

| Material | Contents |
| --- | --- |
| [Adaptation plan](docs/olist/adaptation-plan.md) | Inspected implementation conflicts, target architecture, import/report contracts, and stage checkpoints |
| [Source dictionary](docs/olist/data-dictionary.md) | Identifiers, exact source fields, historical prices/statuses, missing data, and analytical measures |
| [ER model](docs/olist/data-model.md) | Implemented historical facts and simulated seller offers/inventory |
| [Operational rules](docs/stage-04/rules.md) | Offer-level stock strategy, lifecycle, ordered locks, integrity and authorization |
| [Order/inventory API](docs/stage-04/api.md) | Current routes, Docker execution, action semantics, curl workflows and limitations |
| [Stage 4 verification](docs/stage-04/verification.md) | Actual tests, lock observations, HTTP/SQL results and preserved source facts |
| [Stage 4 review](docs/stage-04/review.md) | Independent scope, checks, evidence and remaining limits |
| [Stage 4 files](docs/stage-04/changes.md) | Complete created/changed delivery file inventory |
| [Validated import](docs/stage-03/import.md) | Locked manifest, Docker commands, validation, atomic publication, no-op checks, and report meanings |
| [API guide and examples](docs/stage-03/api.md) | JWT, roles, catalog, historical identifiers, and curl workflows |
| [Stage 3 evidence](docs/stage-03/verification.md) | Actual imports, test/HTTP/schema outcomes, corrections, and limitations |
| [Stage 3 review](docs/stage-03/review.md) | Independent findings, resolutions, and actual reviewer checks |
| [Stage 3 files](docs/stage-03/changes.md) | Complete created/changed file inventory |
| [Current OpenAPI](reports/stage-04/openapi.json) | Validated documentation for implemented endpoints |
| [Docker execution](docs/stage-02/setup.md) | Isolated startup, role separation, checks, and schema restoration |
| [Database implementation](docs/stage-02/database.md) | Reuse, constraints, source clocks, indexes, and service boundaries |
| [Stage 2 verification](docs/stage-02/verification.md) | Actual commands, test results, versions, corrections, and limitations |
| [Stage 2 review](docs/stage-02/review.md) | Independent findings, corrections, checks, and remaining gates |
| [Stage 2 files](docs/stage-02/changes.md) | Complete inventory of created and changed delivery files |
| [Inspection and verification](docs/olist/inspection.md) | Commands, actual counts/anomalies, reproducibility, limitations, and preservation checks |
| [Independent review](docs/olist/review.md) | Conflict corrections, separate profiler rerun, actual checks, and remaining gates |
| [Source manifest](reports/olist/source-manifest.json) | Publisher metadata, version ambiguity, attribution, and archive fingerprint |
| [Executed CSV profile](reports/olist/inspection-profile.json) | Per-file hashes, headers, counts, keys, relationships, and observed anomalies |
| [Data attribution](THIRD_PARTY_DATA.md) | Public source and CC BY-NC-SA 4.0 requirements |
| [Review process](docs/review-process.md) | Independent reviewer, corrections, actual checks, and user approval at each stage |

## Historical facts and explicit simulation

The inspected source contains **99,441 orders, 112,650 item rows, 103,886 payment rows, 32,951 products, and 3,095 sellers**. Historical lines retain their source item sequence, seller, price, freight, and order status. Repeat-customer analysis uses `customer_unique_id`, while order joins use `customer_id`. All figures here are from executed CSV inspection, not SQL analysis.

Historical Olist records are read-only in their own tables and `/api/olist/` namespace, available only to active administrators. They do not create login accounts, stock balances/movements, or simulated approvals. Multiple payment records remain source facts; their amounts are not multiplied by installments or assumed to equal items plus freight.

The operational demonstration uses fictional `example.com` accounts and simulated sellers, offers, current prices and stock movements. New offers start at zero; administrative supply appends audit history. Creation deducts available units, pending cancellation restores them once, and payment/shipping/delivery do not change stock. Purchase, cancellation and inventory writes use ordered PostgreSQL row locks. Historical purchases are never presented as current inventory or today's real offers.

The completed import accepted **451,535 source rows**, represented by **451,537 entities** after building the category union. It rejected no rows and preserved **3,116 inconsistent rows with 3,739 warning issues**. Repeated import verified persisted fields/relationships and returned `NOOP`. Full issue reports stay local; committed summaries contain counts, reconciliation magnitudes, and hashes. These import observations are not index benchmark results.

Raw CSVs, ZIPs, downloaded metadata, and credentials stay outside Git in `.local/` or another local directory. Commit only reviewed aggregate evidence and source/schema metadata. Source-derived outputs retain attribution and the dataset's [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) terms; see the separate data notice for scope.

## Stack and incremental delivery

Actual container versions: Python 3.12.15, Django 5.2.18 LTS, DRF 3.18.3, PostgreSQL 17.11, SimpleJWT 5.5.1, and psycopg 3.3.6. Dependencies are pinned in `requirements.lock`; [runtime evidence](reports/stage-04/runtime.json) records the current environment. Authentication tests exercise login/refresh/access, password/account revocation, privilege changes, and owner/admin boundaries.

| Delivery | Scope | Status |
| --- | --- | --- |
| Adaptation plan | Source/implementation inspection, conflicts, dictionary, ER, import/analysis plan | Reviewed and approved for implementation |
| 2 | Port existing setup; isolated PostgreSQL/roles; historical and seller-offer models, constraints, migrations, schema export | Reviewed and approved |
| 3 | Repeatable Olist import/report; historical read APIs; authentication, customers, catalog, permissions | Reviewed and approved |
| 4 | Multi-seller simulated orders, offer stock/ledger, transitions, rollback/concurrency | Independently reviewed; awaiting user technical review |
| 5 | Executed Olist SQL portfolio and new index experiment with actual plans/samples | Pending |
| 6 | Final English guides, OpenAPI, Docker/import commands, verified curl examples, portfolio presentation | Pending |

An independent reviewer inspects each delivery. Correct material findings, rerun affected checks, publish English commits, and stop for the user's technical review before proceeding. Earlier Stage 1 documents remain historical records and are superseded where the Olist adaptation differs.

## Run the service

```bash
python3 scripts/create_env.py
docker compose build app
docker compose up -d --wait db
docker compose run --rm migrate
docker compose run --rm migrate configure_database_roles
docker compose up -d --wait app
curl --fail --silent --show-error http://127.0.0.1:18020/health/
```

Skip environment generation if `.env` already exists; the generator preserves existing files. The current health response is `{"status":"ok","stage":4}`. The [current execution/API guide](docs/stage-04/api.md) explains startup, inventory and orders; the [import guide](docs/stage-03/import.md) explains historical publication. Registration, JWT, profiles, catalog, customer administration and historical reads remain available. Operational fulfillment/payment are explicit simulations.

## Inspect the source archive

Obtain the archive from its official source, retain the downloaded Kaggle metadata, and compare hashes with the committed manifest. With those local inputs:

```bash
python3 scripts/inspect_olist.py \
  --archive .local/olist/brazilian-ecommerce.zip \
  --metadata .local/olist/kaggle-metadata.json \
  --output .local/olist/inspection-new.json
```

Choose a new output filename each run; the script refuses overwrite. It profiles a ZIP without extracting files or connecting to a database. The separate implemented `import_olist` management command performs validated database publication; use the import guide rather than treating the profiler as an importer. SQL business reports and index measurements remain Stage 5 work.

## Data provenance and licensing

Historical analysis uses the [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). Source attribution, dataset identity, transformations, and CC BY-NC-SA 4.0 obligations are recorded in [THIRD_PARTY_DATA.md](THIRD_PARTY_DATA.md). Operational accounts, inventory, current offer prices, payments, and delivery actions are simulated. This independently developed repository does not claim an Olist employment, contractual, partnership, or endorsement relationship.
