# Order and Inventory Management Service for Olist

A backend service by João Trevisan designed to address order and inventory management needs in Olist's marketplace context. Built with Django REST Framework and PostgreSQL, the solution covers multi-seller orders, seller offers, inventory control, customer access, and sales analytics, with relational integrity and transactional consistency at its core.

Repository: [joaoltrevisan/django-orders-inventory-portfolio](https://github.com/joaoltrevisan/django-orders-inventory-portfolio).

## Current delivery

**Stage 2: isolated PostgreSQL setup, relational models, constraints, migrations, and verified schema export.**

The service now runs in its own Docker Compose environment with restricted database roles and a database-backed health endpoint. Historical Olist records and simulated operational entities have separate models. The executed verification suite passed 39 tests; 75 database authorization checks and schema restoration comparison also passed. Source import, business API endpoints, transaction services, SQL reports, and performance measurements remain scheduled deliveries; previous benchmark results are not evidence for this dataset.

| Material | Contents |
| --- | --- |
| [Adaptation plan](docs/olist/adaptation-plan.md) | Inspected implementation conflicts, target architecture, import/report contracts, and stage checkpoints |
| [Source dictionary](docs/olist/data-dictionary.md) | Identifiers, exact source fields, historical prices/statuses, missing data, and analytical measures |
| [ER model](docs/olist/data-model.md) | Implemented historical facts and simulated seller offers/inventory |
| [Docker execution](docs/stage-02/setup.md) | Isolated startup, role separation, checks, and schema restoration |
| [Database implementation](docs/stage-02/database.md) | Reuse, constraints, source clocks, indexes, and service boundaries |
| [Stage 2 verification](docs/stage-02/verification.md) | Actual commands, test results, versions, corrections, and limitations |
| [Inspection and verification](docs/olist/inspection.md) | Commands, actual counts/anomalies, reproducibility, limitations, and preservation checks |
| [Independent review](docs/olist/review.md) | Conflict corrections, separate profiler rerun, actual checks, and remaining gates |
| [Source manifest](reports/olist/source-manifest.json) | Publisher metadata, version ambiguity, attribution, and archive fingerprint |
| [Executed CSV profile](reports/olist/inspection-profile.json) | Per-file hashes, headers, counts, keys, relationships, and observed anomalies |
| [Data attribution](THIRD_PARTY_DATA.md) | Public source and CC BY-NC-SA 4.0 requirements |
| [Review process](docs/review-process.md) | Independent reviewer, corrections, actual checks, and user approval at each stage |

## Historical facts and explicit simulation

The inspected source contains **99,441 orders, 112,650 item rows, 103,886 payment rows, 32,951 products, and 3,095 sellers**. Historical lines retain their source item sequence, seller, price, freight, and order status. Repeat-customer analysis uses `customer_unique_id`, while order joins use `customer_id`. All figures here are from executed CSV inspection, not SQL analysis.

Historical Olist records will be read-only in their own tables and `/api/olist/` namespace. They do not create login accounts, stock balances/movements, or simulated approvals. Multiple payment records remain source facts; their amounts are not multiplied by installments or assumed to equal items plus freight.

The operational demonstration will retain fictional `example.com` login accounts and simulated sellers, offers, current prices, stock, stock movements, payments, and deliveries. Seller/product offers permit multi-seller orders and independent offer balances. Atomic reservation, strict pending-only cancellation, immutable purchase snapshots, object permissions, and controlled PostgreSQL concurrency remain required. Historical purchases are never presented as current inventory or today's real offers.

Raw CSVs, ZIPs, downloaded metadata, and credentials stay outside Git in `.local/` or another local directory. Commit only reviewed aggregate evidence and source/schema metadata. Source-derived outputs retain attribution and the dataset's [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) terms; see the separate data notice for scope.

## Stack and incremental delivery

Actual container versions: Python 3.12.15, Django 5.2.18 LTS, DRF 3.18.3, PostgreSQL 17.11, SimpleJWT 5.5.1, and psycopg 3.3.6. Dependencies are pinned in `requirements.lock`; [runtime evidence](reports/stage-02/runtime.json) records the complete environment. JWT dependency smoke checks passed; full authentication and permission behavior will be tested with Stage 3 endpoints.

| Delivery | Scope | Status |
| --- | --- | --- |
| Adaptation plan | Source/implementation inspection, conflicts, dictionary, ER, import/analysis plan | Reviewed and approved for implementation |
| 2 | Port existing setup; isolated PostgreSQL/roles; historical and seller-offer models, constraints, migrations, schema export | Implemented; final review pending |
| 3 | Repeatable Olist import/report; historical read APIs; authentication, customers, catalog, permissions | Pending |
| 4 | Multi-seller simulated orders, offer stock/ledger, transitions, rollback/concurrency | Pending |
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

Skip environment generation if `.env` already exists; the generator preserves existing files. The current endpoint returns `{"status":"ok","stage":2}`. The [execution guide](docs/stage-02/setup.md) explains roles, volumes, verification, and safe shutdown. This local server does not yet expose registration, catalog, order, or import endpoints.

## Inspect the source archive

Obtain the archive from its official source, retain the downloaded Kaggle metadata, and compare hashes with the committed manifest. With those local inputs:

```bash
python3 scripts/inspect_olist.py \
  --archive .local/olist/brazilian-ecommerce.zip \
  --metadata .local/olist/kaggle-metadata.json \
  --output .local/olist/inspection-new.json
```

Choose a new output filename each run; the script refuses overwrite. It profiles a ZIP without extracting files or connecting to a database. It is **not** the future validated `import_olist` command. Full download/provenance instructions and actual command outcomes are in the inspection record. Business API examples and import/SQL/benchmark commands will be added and executed with their implementation stages.

## Data provenance and licensing

Historical analysis uses the [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). Source attribution, dataset identity, transformations, and CC BY-NC-SA 4.0 obligations are recorded in [THIRD_PARTY_DATA.md](THIRD_PARTY_DATA.md). Operational accounts, inventory, current offer prices, payments, and delivery actions are simulated. This independently developed repository does not claim an Olist employment, contractual, partnership, or endorsement relationship.
