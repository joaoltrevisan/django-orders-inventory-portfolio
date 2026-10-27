# Public Olist data attribution

This independent educational project uses **Brazilian E-Commerce Public Dataset by Olist**, published by **Olist (`olistbr`)** on [Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). It has no employment, partnership, endorsement, or internal-system relationship with Olist.

The publisher reports **CC BY-NC-SA 4.0**. See the [license summary](https://creativecommons.org/licenses/by-nc-sa/4.0/) and [legal code](https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode.en). Preserve attribution, source/license links and notices; indicate modifications; use the material noncommercially; distribute adapted material under the same license; impose no additional legal or technical restrictions on licensed uses. This notice addresses source data and adapted materials, not a separate software-license grant for application code.

Source inspection date: **2026-10-26**. The API reports current version **2**, updated **2021-10-01**, but also lists historical version 7 and another version 2. The inspected snapshot is therefore identified by hashes, not the version label alone:

`967e41e04fc306fe604e2a693f488995a8b41e5047418f8a5c8e4abd6deca784`

The [source manifest](reports/olist/source-manifest.json) records the retrieved metadata fields and archive identity. The [aggregate profile](reports/olist/inspection-profile.json) records each CSV's hash, headers, row count, and observed quality flags. Raw CSVs, ZIPs, and downloaded metadata stay outside Git. The implementation imports validated historical rows into normalized relational tables, retains source identifiers/statuses/decimal amounts, normalizes documented column names, builds a category-key union and stores raw plus parsed timezone-free timestamps. It preserves representable anomalies with warning issues rather than repairing facts. Reviews/geolocation are fingerprinted but deferred. [The dictionary](docs/olist/data-dictionary.md) records mappings; the [import report](reports/stage-05/benchmark-import.json) and [SQL evidence](reports/stage-05/sql-results.json) disclose actual counts, transformations, hashes and derived analyses.

Source-derived profiles/reports distributed here retain the dataset attribution and CC BY-NC-SA 4.0 terms. Simulated accounts, prices, inventory, stock movements, new payments, and operational delivery events are explicitly separate from source facts.

Recorded retrieval precision is the calendar date only. The stored snapshot timestamp encodes a conventional UTC day boundary, not an observed download instant. Source event timestamps have no verified timezone and are not silently converted into UTC instants. Historical item prices are never described as current real catalog prices, and recorded payment rows are never represented as newly processed charges.
