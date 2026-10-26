# Olist E-Commerce: Independent Back-End Case Study

An independent educational project using the public [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) to demonstrate Django/DRF development, PostgreSQL modeling and integrity, transactional marketplace simulation, SQL analysis, testing, and measured query optimization.

This project does not imply employment, partnership, endorsement, or access to Olist's internal systems. Repository: [joaoltrevisan/django-orders-inventory-portfolio](https://github.com/joaoltrevisan/django-orders-inventory-portfolio).

## Current delivery

**Olist adaptation plan and executed source inspection; awaiting technical review before implementation.**

The real archive has been downloaded and profiled. This repository contains design documents and a repeatable read-only CSV inspection script. The existing related API will be adapted incrementally; no API has yet been ported here, no database import has run, and no Olist SQL or performance experiment has been executed. Previous test counts and benchmark results are not evidence for this dataset.

| Material | Contents |
| --- | --- |
| [Adaptation plan](docs/olist/adaptation-plan.md) | Inspected implementation conflicts, target architecture, import/report contracts, and stage checkpoints |
| [Source dictionary](docs/olist/data-dictionary.md) | Identifiers, exact source fields, historical prices/statuses, missing data, and analytical measures |
| [Proposed ER model](docs/olist/data-model.md) | Separate historical facts and simulated seller offers/inventory |
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

Keep Python 3.12, Django 5.2 LTS, DRF, PostgreSQL 17, JWT, Docker/Compose, and PostgreSQL automated tests. The [initial environment assessment](docs/stage-01/assessment.md) records previously observed pins and the open JWT compatibility check. Stage 2 must reproduce and record the new environment actually used.

| Delivery | Scope | Status |
| --- | --- | --- |
| Adaptation plan | Source/implementation inspection, conflicts, dictionary, ER, import/analysis plan | Current review delivery |
| 2 | Port existing setup; isolated PostgreSQL/roles; historical and seller-offer models, constraints, migrations, schema export | Pending |
| 3 | Repeatable Olist import/report; historical read APIs; authentication, customers, catalog, permissions | Pending |
| 4 | Multi-seller simulated orders, offer stock/ledger, transitions, rollback/concurrency | Pending |
| 5 | Executed Olist SQL portfolio and new index experiment with actual plans/samples | Pending |
| 6 | Final English guides, OpenAPI, Docker/import commands, verified curl examples, portfolio presentation | Pending |

An independent reviewer inspects each delivery. Correct material findings, rerun affected checks, publish English commits, and stop for the user's technical review before proceeding. Earlier Stage 1 documents remain historical records and are superseded where the Olist adaptation differs.

## Run the current inspection

Obtain the archive from its official source, retain the downloaded Kaggle metadata, and compare hashes with the committed manifest. With those local inputs:

```bash
python3 scripts/inspect_olist.py \
  --archive .local/olist/brazilian-ecommerce.zip \
  --metadata .local/olist/kaggle-metadata.json \
  --output .local/olist/inspection-new.json
```

Choose a new output filename each run; the script refuses overwrite. It profiles a ZIP without extracting files or connecting to a database. It is **not** the future validated `import_olist` command. Full download/provenance instructions and actual command outcomes are in the inspection record. Application startup, database creation/import, API examples, and SQL/benchmark commands will be added and executed with their implementation stages.
