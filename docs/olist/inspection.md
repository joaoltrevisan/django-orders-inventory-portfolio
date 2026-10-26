# Olist adaptation: executed inspection and verification

Date: 2026-10-26. This delivery is a revised plan with source inspection, not an application or import implementation. See the [adaptation plan](adaptation-plan.md), [dictionary](data-dictionary.md), and [proposed model](data-model.md).

## Inspected implementation

Before creating adaptation files, inspected the new repository's status, recent commits, file inventory, README, Stage 1 requirements, and reviewer workflow. It was clean at `3a40eba` and contained no application code. Inspected the reusable API's accounts/catalog/inventory/orders models, order creation service, report selectors, configuration/dependencies, and Git status. It was clean at `21b5b17`. No local Olist CSV/archive was found in the initial workspace search.

Commands included `git status --short --branch`, `git log`, filtered `rg --files`, and source reads in each repository. Existing files and data were preserved; no database connection, migration, importer, Docker workload, or simulation operation was run.

## Source retrieval and identity

The publisher's page is [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). Read metadata from `https://www.kaggle.com/api/v1/datasets/view/olistbr/brazilian-ecommerce` and downloaded the public ZIP from `https://www.kaggle.com/api/v1/datasets/download/olistbr/brazilian-ecommerce` using macOS curl with TLS verification enabled. Input files initially went into a fresh temporary directory, then copies of the complete archive/metadata were retained under ignored `.local/olist/` for reproducible local checks.

Observed archive: **44,717,580 bytes**; `zipfile.ZipFile.testzip()` returned `None`, meaning no member failed the ZIP integrity test. Archive SHA-256:

`967e41e04fc306fe604e2a693f488995a8b41e5047418f8a5c8e4abd6deca784`

The [manifest](../../reports/olist/source-manifest.json) records the source URL, retrieved date, public publisher metadata, license, and version ambiguity. Metadata reports current version 2 updated on 2021-10-01, while its history also lists version 7 and a second version 2. Do not conceal that ambiguity or describe the ZIP as proven by a unique version number alone. Member hashes in the [profile](../../reports/olist/inspection-profile.json) identify the exact bytes inspected.

Actual retrieval failures:

- The first Python 3.14 `urllib.request` attempt exited 1 with local certificate-chain verification failure. No TLS verification was disabled. Using `/usr/bin/curl --fail --location --silent --show-error --max-time 60` succeeded for metadata and the complete latest ZIP.
- An additional download using `?datasetVersionNumber=2` timed out with curl exit 28 after a partial transfer. That incomplete file remains outside Git and was not profiled, accepted as an archive, or used as version-equivalence evidence. A future downloader must verify the locked archive/member hashes and refuse silently changed input.

To obtain a fresh local candidate without overwriting existing inputs:

```bash
mkdir -p .local
mkdir .local/olist-download
curl --fail --location --silent --show-error --max-time 60 \
  --output .local/olist-download/kaggle-metadata.json \
  https://www.kaggle.com/api/v1/datasets/view/olistbr/brazilian-ecommerce
curl --fail --location --silent --show-error --max-time 60 \
  --output .local/olist-download/brazilian-ecommerce.zip \
  https://www.kaggle.com/api/v1/datasets/download/olistbr/brazilian-ecommerce
```

The new directory must not already exist. Stop if a command fails; do not treat a partial ZIP as valid. Run the profiler on a complete candidate and compare its fingerprint with the committed profile before using it as the same snapshot. These are source-download/inspection instructions, not the future database-import command.

## Actual CSV observations

| File | Rows |
| --- | ---: |
| Customers | 99,441 |
| Orders | 99,441 |
| Order items | 112,650 |
| Payment records | 103,886 |
| Products | 32,951 |
| Sellers | 3,095 |
| Category translations | 71 |
| Reviews, deferred from initial import | 99,224 |
| Geolocation, deferred from initial import | 1,000,163 |

Executed checks found zero duplicate rows under the seven imported-scope source keys and zero missing parents for order/customer, item/order/product/seller, and payment/order references. This is a statement about these checks on this archive, not proof that every value is valid.

Important observed cardinality/quality facts:

- 96,096 distinct `customer_unique_id` values; 2,997 have more than one order across **all** statuses in this snapshot. This is an inspection count, not the later delivered-order repeat-customer SQL metric.
- 1,278 orders with multiple sellers; 9,803 with multiple item rows; 7,088 repeated order/product groups. Source line sequences must remain intact.
- 34,448 distinct product/seller pairs; 5,435 have multiple observed historical prices. No current operational price can be inferred from this fact.
- 2,961 orders with multiple payment rows; 275 have both multiple item rows and multiple payment rows, making unaggregated joins unsafe for totals.
- 775 orders have no item rows; 1 has no payment rows. Preserve these orders.
- 9 payments have zero value; 2 have zero installments. Do not force simulation-only constraints onto these facts.
- 610 products lack categories. Two nonblank categories lack an English translation, covering 13 products. Keep source keys and nullable English labels.
- Of 96,478 source `delivered` orders, 14 lack approval, 2 lack carrier-delivery, and 8 lack customer-delivery timestamps. These categories can overlap and must not be added as distinct-order counts without deduplication.
- 6 `canceled` orders contain customer-delivery timestamps. Preserve source values and flag them rather than inventing cancellation/return chronology.
- Among 98,665 orders with both item and payment facts, 98,089 amounts match exactly; 303 have absolute differences above BRL 0.01 for `payment_sum - (item_price_sum + freight_sum)`. Maximum absolute difference is BRL 182.81. The remaining differences are nonzero but no larger than BRL 0.01. None was repaired.

Purchase timestamps range from `2016-09-04 21:15:19` to `2018-10-17 17:30:18` as source-local text. Their time zone was not established. No SQL sales, delivery-time, or performance results are claimed from this CSV inspection.

## Repeatable inspection command

```bash
python3 scripts/inspect_olist.py \
  --archive .local/olist/brazilian-ecommerce.zip \
  --metadata .local/olist/kaggle-metadata.json \
  --output .local/olist/inspection-new.json
```

The script reads the ZIP without extraction, computes aggregate evidence, and creates a new output exclusively. It does not connect to a database, download credentials, repair rows, or implement the planned importer. It is designed for this inspected schema; it is not a general untrusted-archive ingestion service. Review free text is neither published nor retained in its reports.

Initial profiling ran with host Python 3.14.7; the same profiler also ran successfully with the existing selected-runtime Python 3.12.15 and produced an identical JSON profile. Ruff 0.17.2 is reused as a local inspection tool, not installed as a new application dependency. Actual repeatability, overwrite-protection, documentation, independent-review, and preservation results are recorded in the [review record](review.md).

## Limits and next delivery

Raw inputs remain local/ignored. Only the read-only inspection script, aggregate JSON evidence, source/license notice, and English design/review documents are eligible for publication. Source-derived outputs retain attribution and CC BY-NC-SA 4.0 terms.

Mermaid is provided as source; rendering is not yet verified. PostgreSQL import, query correctness, permissions, simulation concurrency, and index measurements remain unexecuted and require their implementation-stage tests. Do not interpret a successful profiler or reviewer opinion as a passing application suite or approval to proceed automatically.
