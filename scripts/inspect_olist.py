"""Profile a local Olist ZIP without extracting files or changing a database."""

import argparse
import csv
import hashlib
import io
import json
import zipfile
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

KEYS = {
    "olist_customers_dataset.csv": ("customer_id",),
    "olist_orders_dataset.csv": ("order_id",),
    "olist_order_items_dataset.csv": ("order_id", "order_item_id"),
    "olist_order_payments_dataset.csv": ("order_id", "payment_sequential"),
    "olist_products_dataset.csv": ("product_id",),
    "olist_sellers_dataset.csv": ("seller_id",),
    "product_category_name_translation.csv": ("product_category_name",),
}


def profile_archive(archive, metadata):
    """Return observed counts and anomalies, not an import validation verdict."""
    tables, files = {}, {}
    with zipfile.ZipFile(archive) as source:
        bad_member = source.testzip()
        if bad_member is not None:
            raise ValueError(f"ZIP integrity check failed: {bad_member}")
        names = source.namelist()
        if len(names) != len(set(names)):
            raise ValueError("ZIP contains duplicate member names.")
        if not set(KEYS).issubset(names):
            raise ValueError("ZIP is missing required Olist CSV files.")
        for name in names:
            if not name.endswith(".csv"):
                continue
            content = source.read(name)
            reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
            rows, blanks, count = [], Counter(), 0
            for row in reader:
                count += 1
                blanks.update(key for key, value in row.items() if value in ("", None))
                if name in KEYS:
                    rows.append(row)
            files[name] = {
                "rows": count,
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "columns": reader.fieldnames,
                "blank_cells_by_column": dict(blanks),
            }
            if name in KEYS:
                tables[name] = rows
                fields = KEYS[name]
                counts = Counter(tuple(row[field] for field in fields) for row in rows)
                files[name]["key"] = list(fields)
                files[name]["duplicate_key_rows"] = sum(
                    value - 1 for value in counts.values()
                )

    customers = tables["olist_customers_dataset.csv"]
    orders = tables["olist_orders_dataset.csv"]
    items = tables["olist_order_items_dataset.csv"]
    payments = tables["olist_order_payments_dataset.csv"]
    products = tables["olist_products_dataset.csv"]
    sellers = tables["olist_sellers_dataset.csv"]
    translations = tables["product_category_name_translation.csv"]
    customer_ids = {row["customer_id"] for row in customers}
    order_ids = {row["order_id"] for row in orders}
    product_ids = {row["product_id"] for row in products}
    seller_ids = {row["seller_id"] for row in sellers}
    customer_map = {row["customer_id"]: row["customer_unique_id"] for row in customers}
    customer_orders = Counter(customer_map[row["customer_id"]] for row in orders)
    order_sellers = defaultdict(set)
    item_counts, payment_counts, order_products = Counter(), Counter(), Counter()
    pair_prices = defaultdict(set)
    item_totals, payment_totals = defaultdict(Decimal), defaultdict(Decimal)
    for row in items:
        order_id = row["order_id"]
        order_sellers[order_id].add(row["seller_id"])
        item_counts[order_id] += 1
        order_products[(order_id, row["product_id"])] += 1
        pair_prices[(row["product_id"], row["seller_id"])].add(Decimal(row["price"]))
        item_totals[order_id] += Decimal(row["price"]) + Decimal(row["freight_value"])
    for row in payments:
        payment_counts[row["order_id"]] += 1
        payment_totals[row["order_id"]] += Decimal(row["payment_value"])
    category_keys = {row["product_category_name"] for row in translations}
    categories = Counter(row["product_category_name"] for row in products)
    common = item_totals.keys() & payment_totals.keys()
    differences = [payment_totals[key] - item_totals[key] for key in common]
    with archive.open("rb") as handle:
        archive_hash = hashlib.file_digest(handle, "sha256").hexdigest()
    return {
        "source": {
            "dataset_ref": "olistbr/brazilian-ecommerce",
            "publisher_current_version_reported": metadata.get("currentVersionNumber"),
            "publisher_last_updated": metadata.get("lastUpdated"),
            "publisher_license_reported": metadata.get("licenseName"),
            "publisher_version_history_numbers": [
                row["versionNumber"] for row in metadata.get("versions", [])
            ],
            "version_note": "Publisher labels are ambiguous; archive and member hashes identify the inspected snapshot.",
            "archive_bytes": archive.stat().st_size,
            "archive_sha256": archive_hash,
        },
        "files": files,
        "relationships": {
            "orders_with_missing_customer": sum(
                row["customer_id"] not in customer_ids for row in orders
            ),
            "items_with_missing_order": sum(
                row["order_id"] not in order_ids for row in items
            ),
            "items_with_missing_product": sum(
                row["product_id"] not in product_ids for row in items
            ),
            "items_with_missing_seller": sum(
                row["seller_id"] not in seller_ids for row in items
            ),
            "payments_with_missing_order": sum(
                row["order_id"] not in order_ids for row in payments
            ),
            "distinct_customer_unique_ids": len(customer_orders),
            "repeat_customer_unique_ids_all_statuses": sum(
                value > 1 for value in customer_orders.values()
            ),
            "orders_with_multiple_sellers": sum(
                len(value) > 1 for value in order_sellers.values()
            ),
            "orders_with_multiple_items": sum(
                value > 1 for value in item_counts.values()
            ),
            "orders_with_multiple_payment_rows": sum(
                value > 1 for value in payment_counts.values()
            ),
            "orders_with_multiple_items_and_payment_rows": sum(
                item_counts[key] > 1 and payment_counts[key] > 1 for key in order_ids
            ),
            "repeated_order_product_groups": sum(
                value > 1 for value in order_products.values()
            ),
            "distinct_product_seller_pairs": len(pair_prices),
            "product_seller_pairs_with_multiple_prices": sum(
                len(value) > 1 for value in pair_prices.values()
            ),
            "orders_without_items": len(order_ids - item_counts.keys()),
            "orders_without_payments": len(order_ids - payment_counts.keys()),
            "max_order_item_id": max(int(row["order_item_id"]) for row in items),
            "payment_types": dict(Counter(row["payment_type"] for row in payments)),
            "zero_value_payments": sum(
                Decimal(row["payment_value"]) == 0 for row in payments
            ),
            "zero_installment_payments": sum(
                int(row["payment_installments"]) == 0 for row in payments
            ),
            "minimum_item_price": str(min(Decimal(row["price"]) for row in items)),
            "minimum_freight_value": str(
                min(Decimal(row["freight_value"]) for row in items)
            ),
            "categories_missing_english_translation": {
                key: value
                for key, value in sorted(categories.items())
                if key and key not in category_keys
            },
        },
        "orders": {
            "statuses": dict(Counter(row["order_status"] for row in orders)),
            "minimum_purchase_timestamp": min(
                row["order_purchase_timestamp"] for row in orders
            ),
            "maximum_purchase_timestamp": max(
                row["order_purchase_timestamp"] for row in orders
            ),
            "delivered_missing_approval": sum(
                row["order_status"] == "delivered" and not row["order_approved_at"]
                for row in orders
            ),
            "delivered_missing_carrier_timestamp": sum(
                row["order_status"] == "delivered"
                and not row["order_delivered_carrier_date"]
                for row in orders
            ),
            "delivered_missing_customer_timestamp": sum(
                row["order_status"] == "delivered"
                and not row["order_delivered_customer_date"]
                for row in orders
            ),
            "cancelled_with_delivery_timestamp": sum(
                row["order_status"] == "canceled"
                and bool(row["order_delivered_customer_date"])
                for row in orders
            ),
            "delivery_before_purchase": sum(
                bool(row["order_delivered_customer_date"])
                and row["order_delivered_customer_date"]
                < row["order_purchase_timestamp"]
                for row in orders
            ),
        },
        "reconciliation": {
            "orders_with_items_and_payments": len(common),
            "exact_amount_matches": sum(value == 0 for value in differences),
            "absolute_difference_above_001": sum(
                abs(value) > Decimal("0.01") for value in differences
            ),
            "max_absolute_difference": str(max(abs(value) for value in differences)),
            "note": "Compare payment sums with item price plus freight. Differences are flags. Never multiply by installments.",
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    result = profile_archive(args.archive, metadata)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print("Profile complete. No database connection or extraction was performed.")


if __name__ == "__main__":
    main()
