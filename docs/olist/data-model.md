# Olist case-study ER model

Status: implemented as Stage 2 models/migrations in an isolated PostgreSQL database. The diagram highlights core fields; the complete generated DDL is in `sql/schema.sql`. Historical import and operational services remain later-stage work. The initial Stage 1 model stays archived.

## Historical domain

```mermaid
erDiagram
    olist_dataset_snapshot o|--o{ olist_import_run : records_attempts
    olist_import_run ||--o{ olist_import_issue : reports
    olist_dataset_snapshot ||--o{ olist_customer : identifies_snapshot
    olist_dataset_snapshot ||--o{ olist_product : identifies_snapshot
    olist_dataset_snapshot ||--o{ olist_category : identifies_snapshot
    olist_dataset_snapshot ||--o{ olist_seller : identifies_snapshot
    olist_dataset_snapshot ||--o{ olist_order : identifies_snapshot
    olist_category o|--o{ olist_product : classifies
    olist_customer ||--o{ olist_order : referenced_by
    olist_order ||--o{ olist_order_item : contains
    olist_product ||--o{ olist_order_item : purchased_as
    olist_seller ||--o{ olist_order_item : fulfills
    olist_order ||--o{ olist_payment_record : has_records

    olist_dataset_snapshot {
        bigint id PK
        smallint singleton UK "Database CHECK equals 1"
        varchar dataset_ref
        varchar reported_version
        varchar archive_sha256 UK
        jsonb member_manifest
        varchar mapping_version
        varchar publication_status
        timestamptz retrieved_at
    }
    olist_import_run {
        bigint id PK
        bigint snapshot_id FK "Nullable before validation completes"
        varchar status
        jsonb counts
        timestamptz started_at
        timestamptz finished_at
    }
    olist_import_issue {
        bigint id PK
        bigint run_id FK
        varchar file_name
        integer source_row_number
        varchar source_key
        varchar issue_code
        varchar severity
    }
    olist_customer {
        bigint id PK
        bigint snapshot_id FK
        varchar source_customer_id UK
        varchar customer_unique_id "Nonunique indexed repeat identity"
        varchar zip_code_prefix
        varchar city
        varchar state
    }
    olist_category {
        bigint id PK
        bigint snapshot_id FK
        varchar source_name UK
        varchar english_name "Nullable"
    }
    olist_product {
        bigint id PK
        bigint snapshot_id FK
        varchar source_product_id UK
        bigint category_id FK "Nullable"
        integer name_length "Nullable, not a name"
        integer description_length "Nullable"
        integer weight_g "Nullable"
    }
    olist_seller {
        bigint id PK
        bigint snapshot_id FK
        varchar source_seller_id UK
        varchar zip_code_prefix
        varchar city
        varchar state
    }
    olist_order {
        bigint id PK
        bigint snapshot_id FK
        varchar source_order_id UK
        bigint customer_id FK
        varchar source_status
        varchar purchased_at_raw
        timestamp purchased_at_source "Without time zone"
        timestamp approved_at_source "Nullable"
        timestamp delivered_carrier_at_source "Nullable"
        timestamp delivered_customer_at_source "Nullable"
        timestamp estimated_delivery_at_source "Nullable"
    }
    olist_order_item {
        bigint id PK
        bigint order_id FK
        integer source_order_item_id "Unique with order_id"
        bigint product_id FK
        bigint seller_id FK
        numeric price "Historical source amount"
        numeric freight_value
        timestamp shipping_limit_at_source
    }
    olist_payment_record {
        bigint id PK
        bigint order_id FK
        integer payment_sequential "Unique with order_id"
        varchar payment_type
        integer payment_installments
        numeric payment_value "Recorded amount, not simulated processing"
    }
```

The diagram highlights core fields. All source timestamp columns retain matching raw text, not just purchase time; additional product measurements map as listed in the dictionary. A source order may have zero item/payment rows. Historical customers have no Django user FK. Their `customer_unique_id` intentionally repeats. The archive happens to use one customer row per order; a conventional FK preserves source references without asserting a universal business rule beyond this snapshot.

`DatasetSnapshot` identifies an accepted source. Stage 2 enforces exactly one possible snapshot identity through a nonnull unique `singleton` column constrained to 1, with unique source identifiers. All historical parent relationships use protected FKs. `ImportRun` can exist before a snapshot is accepted. The Stage 3 importer must validate matching source identity and atomically publish completed snapshots with their domain inserts; that workflow is not implemented yet. A future multi-snapshot design would need additional cross-snapshot integrity enforcement rather than relying on separate ordinary FKs.

Historical item uniqueness is `(order_id, source_order_item_id)` and payment uniqueness is `(order_id, payment_sequential)`. Do not add `(order_id, product_id)` uniqueness. Integer sequences must be positive and source money finite/nonnegative, with reviewed numeric widths. Preserve zero payment values and zero installments. Do not apply operational state/timestamp, nonempty-order, exact-payment-total, or simulated-snapshot-name checks to historical rows.

Keep missing product categories nullable. Build category identities from the union of nonblank product category keys and supplied translations, so untranslated categories retain their identity. Their English label stays null; presentation may use an English `Untranslated category` label alongside the original source key.

## Simulated marketplace domain

```mermaid
erDiagram
    accounts_user ||--o| accounts_customer : has_demo_profile
    accounts_customer ||--o{ orders_order : places
    catalog_seller ||--o{ catalog_offer : offers
    catalog_product ||--o{ catalog_offer : listed_as
    catalog_offer ||--o| inventory_stock : has_simulated_balance
    orders_order ||--o{ orders_order_item : contains
    catalog_offer ||--o{ orders_order_item : purchased_offer
    catalog_offer ||--o{ inventory_stock_movement : has_simulated_history
    orders_order o|--o{ inventory_stock_movement : contextualizes
    accounts_user ||--o{ inventory_stock_movement : performs
    orders_order ||--o| orders_simulated_payment : has_simulated_approval
    orders_order ||--o| orders_shipment : has_simulated_delivery

    catalog_offer {
        bigint id PK
        bigint seller_id FK "Unique with product_id"
        bigint product_id FK
        numeric simulated_price
        boolean is_active
    }
    inventory_stock {
        bigint id PK
        bigint offer_id FK,UK
        integer available_quantity
    }
    orders_order_item {
        bigint id PK
        bigint order_id FK
        bigint offer_id FK "Unique with order_id"
        integer quantity
        numeric unit_price "Simulated purchase snapshot"
        varchar product_sku
        varchar product_name
        varchar seller_label
    }
    inventory_stock_movement {
        bigint id PK
        bigint offer_id FK
        bigint order_id FK "Nullable by movement type"
        bigint performed_by_id FK
        varchar movement_type
        integer quantity_delta
        varchar reason
        timestamptz created_at
    }
```

These table names are now explicit in Stage 2 models/migrations and agree with the SQL export. The offer reassignment trigger enforces immutable seller/product associations, including raw SQL and bulk updates. Operational FKs, positive decimal prices/quantities, nonnegative stock, history protection, and strict lifecycle checks remain. Offer seller/product associations are immutable; changing an association requires a new offer, not rewriting purchase identity. Reservation/release uniqueness changes to `(order, offer, movement_type)`; cancellation headroom is calculated per offer. Names/labels and current prices here are fictional, never fields copied into the historical catalog as facts.

Optional later historical provenance links are deliberately omitted from the core diagram because they are not operational ownership, authentication, or current-merchant relationships. No historical customer-to-login linkage will be created. A demo seed using historical product/seller references must label its projection and synthetic attributes explicitly.

## Constraints, indexes, and locks

Historical baseline indexes include PKs, unique source identifiers, item/payment composite keys, FKs, and a nonunique index on `customer_unique_id`. Avoid duplicate indexes already supplied by uniqueness/FKs. Candidate purchase-date/status/seller-report indexes need new measurements on the actual imported snapshot before adoption as performance improvements.

Simulation locks follow existing order -> sellers by ID -> products by ID -> offers by ID -> stock by offer ID. Catalog activation/price edits and stock changes must follow the same relative order. Historical importer publication uses its own database-scoped lock, and API readers cannot mutate historical facts.

PostgreSQL constraints enforce relational references and local ranges/keys; application services enforce operational cross-table totals, snapshot immutability, legal transitions, and ledger reconciliation. Import validation/reporting preserves historical exceptions instead of forcing operational invariants. The [adaptation plan](adaptation-plan.md) defines the required tests and incremental delivery boundaries.
