"""Validate a locked Olist archive and atomically publish one immutable snapshot."""

import csv
import hashlib
import io
import json
import re
import time
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.db import connection, transaction
from django.utils import timezone

from .fields import SourceDateTimeField
from .models import (
    Category,
    DatasetSnapshot,
    HistoricalCustomer,
    HistoricalOrder,
    HistoricalOrderItem,
    HistoricalPaymentRecord,
    HistoricalProduct,
    HistoricalSeller,
    ImportIssue,
    ImportRun,
)

MAPPING_VERSION = "olist-1"
IMPORT_LOCK = (73019, 3)
FILES = {
    "customers": "olist_customers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "items": "olist_order_items_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "translations": "product_category_name_translation.csv",
}
MODELS = {
    "categories": Category,
    "customers": HistoricalCustomer,
    "products": HistoricalProduct,
    "sellers": HistoricalSeller,
    "orders": HistoricalOrder,
    "items": HistoricalOrderItem,
    "payments": HistoricalPaymentRecord,
}
KEYS = {
    "customers": ("customer_id",),
    "products": ("product_id",),
    "sellers": ("seller_id",),
    "orders": ("order_id",),
    "items": ("order_id", "order_item_id"),
    "payments": ("order_id", "payment_sequential"),
    "translations": ("product_category_name",),
}
TIMES = {
    "order_purchase_timestamp": "purchased_at",
    "order_approved_at": "approved_at",
    "order_delivered_carrier_date": "delivered_carrier_at",
    "order_delivered_customer_date": "delivered_customer_at",
    "order_estimated_delivery_date": "estimated_delivery_at",
}
PRODUCT_INTS = {
    "product_name_lenght": "name_length",
    "product_description_lenght": "description_length",
    "product_photos_qty": "photos_count",
    "product_weight_g": "weight_g",
    "product_length_cm": "length_cm",
    "product_height_cm": "height_cm",
    "product_width_cm": "width_cm",
}
SOURCE_STATUSES = {
    "delivered",
    "shipped",
    "canceled",
    "unavailable",
    "invoiced",
    "processing",
    "created",
    "approved",
}


class ImportFailure(Exception):
    def __init__(self, code, report):
        super().__init__(code)
        self.report = report
        self.code = code


def scalar(value):
    if isinstance(value, Decimal):
        return format(value, ".2f")
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value


def content_hash(rows):
    """Hash complete canonical row content independently of surrogate IDs/order."""
    serialized = sorted(
        json.dumps({k: scalar(v) for k, v in row.items()}, sort_keys=True, ensure_ascii=False)
        for row in rows
    )
    return hashlib.sha256("\n".join(serialized).encode()).hexdigest()


def text(row, field, length, *, optional=False, pattern=None):
    value = row[field]
    if value is None or not isinstance(value, str) or "\x00" in value:
        raise ValueError(f"INVALID_TEXT:{field}")
    if len(value) > length or (not optional and not value.strip()):
        raise ValueError(f"INVALID_TEXT:{field}")
    if pattern and not re.fullmatch(pattern, value):
        raise ValueError(f"INVALID_FORMAT:{field}")
    return value


def source_id(row, field):
    return text(row, field, 32, pattern=r"[0-9a-f]{32}")


def integer(row, field, *, minimum=0, optional=False):
    value = row[field]
    if value == "" and optional:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+", value):
        raise ValueError(f"INVALID_INTEGER:{field}")
    if not minimum <= int(value) <= 2147483647:
        raise ValueError(f"INTEGER_RANGE:{field}")
    return int(value)


def money(row, field):
    value = row[field]
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,14}(?:\.[0-9]{1,2})?", value):
        raise ValueError(f"INVALID_MONEY:{field}")
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"INVALID_MONEY:{field}") from error
    if not result.is_finite() or not 0 <= result <= Decimal("99999999999999.99"):
        raise ValueError(f"MONEY_RANGE:{field}")
    return result


def timestamp(row, field, prefix, *, required=False):
    value = text(row, field, 19, optional=not required)
    parsed = SourceDateTimeField().to_python(value) if value else None
    return {prefix + "_raw": value, prefix + "_source": parsed}


def parse_row(entity, row):
    if entity in {"customers", "sellers"}:
        prefix = "customer" if entity == "customers" else "seller"
        values = {
            "source_" + prefix + "_id": source_id(row, prefix + "_id"),
            "zip_code_prefix": text(row, prefix + "_zip_code_prefix", 5, pattern=r"[0-9]{5}"),
            "city": text(row, prefix + "_city", 200),
            "state": text(row, prefix + "_state", 2, pattern=r"[A-Z]{2}"),
        }
        if entity == "customers":
            values["customer_unique_id"] = source_id(row, "customer_unique_id")
        return values
    if entity == "translations":
        return {
            "source_name": text(row, "product_category_name", 200),
            "english_name": text(row, "product_category_name_english", 200, optional=True) or None,
        }
    if entity == "products":
        return {
            "source_product_id": source_id(row, "product_id"),
            "category__source_name": text(row, "product_category_name", 200, optional=True) or None,
            **{
                target: integer(row, field, optional=True) for field, target in PRODUCT_INTS.items()
            },
        }
    if entity == "orders":
        values = {
            "source_order_id": source_id(row, "order_id"),
            "customer__source_customer_id": source_id(row, "customer_id"),
            "source_status": text(row, "order_status", 50),
        }
        for field, prefix in TIMES.items():
            values.update(
                timestamp(row, field, prefix, required=field == "order_purchase_timestamp")
            )
        return values
    if entity == "items":
        return {
            "order__source_order_id": source_id(row, "order_id"),
            "source_order_item_id": integer(row, "order_item_id", minimum=1),
            "product__source_product_id": source_id(row, "product_id"),
            "seller__source_seller_id": source_id(row, "seller_id"),
            "price": money(row, "price"),
            "freight_value": money(row, "freight_value"),
            **timestamp(row, "shipping_limit_date", "shipping_limit_at", required=True),
        }
    return {
        "order__source_order_id": source_id(row, "order_id"),
        "payment_sequential": integer(row, "payment_sequential", minimum=1),
        "payment_type": text(row, "payment_type", 50),
        "payment_installments": integer(row, "payment_installments"),
        "payment_value": money(row, "payment_value"),
    }


def add_issue(report, entity, row, key, code, severity="WARNING"):
    key = re.sub(r"[\x00-\x1f\x7f]", lambda match: f"\\u{ord(match[0]):04x}", key)
    report["issues"].append(
        {
            "file_name": FILES.get(entity, entity),
            "source_row_number": row,
            "source_key": key[:200],
            "issue_code": code,
            "severity": severity,
        }
    )


def validate_archive(archive, manifest, report):
    from django.core.exceptions import ValidationError

    if manifest["dataset_ref"] != "olistbr/brazilian-ecommerce" or (
        manifest["license"] != "CC BY-NC-SA 4.0" or manifest["mapping_version"] != MAPPING_VERSION
    ):
        raise ValueError("UNSUPPORTED_MANIFEST")
    if not isinstance(manifest.get("source_url"), str):
        raise ValueError("INVALID_SOURCE_URL")
    try:
        DatasetSnapshot._meta.get_field("source_url").clean(manifest["source_url"], None)
    except ValidationError as error:
        raise ValueError("INVALID_SOURCE_URL") from error
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", manifest["retrieved_on"]):
        raise ValueError("INVALID_RETRIEVAL_DATE")
    datetime.strptime(manifest["retrieved_on"], "%Y-%m-%d")
    if (
        not isinstance(manifest["reported_version"], str)
        or not 1 <= len(manifest["reported_version"]) <= 100
    ):
        raise ValueError("INVALID_REPORTED_VERSION")
    with archive.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    if digest != manifest["archive_sha256"]:
        raise ValueError("ARCHIVE_HASH_MISMATCH")
    report["archive_sha256"] = digest
    parsed = {entity: [] for entity in FILES}
    with zipfile.ZipFile(archive) as source:
        names = source.namelist()
        if len(names) != len(set(names)) or set(names) != set(manifest["files"]):
            raise ValueError("ARCHIVE_MEMBERS_MISMATCH")
        if not set(FILES.values()).issubset(names):
            raise ValueError("MISSING_REQUIRED_FILE")
        # Never extract ZIP paths. Check even intentionally deferred members.
        for name in names:
            expected = manifest["files"][name]
            if (
                source.getinfo(name).file_size != expected["bytes"]
                or expected["bytes"] > 100_000_000
            ):
                raise ValueError("MEMBER_SIZE_MISMATCH")
            data = source.read(name)
            if hashlib.sha256(data).hexdigest() != expected["sha256"]:
                raise ValueError("MEMBER_HASH_MISMATCH")
            reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
            if reader.fieldnames != expected["columns"] or len(set(reader.fieldnames)) != len(
                reader.fieldnames
            ):
                raise ValueError("HEADER_MISMATCH")
            entity = next((key for key, filename in FILES.items() if filename == name), None)
            if entity is None:
                report["deferred_files"][name] = expected["rows"]
                continue
            counts = {
                key: 0
                for key in [
                    "input",
                    "accepted",
                    "duplicate_input",
                    "rejected",
                    "imported",
                    "skipped",
                ]
            }
            report["files"][name] = counts
            seen = set()
            for number, row in enumerate(reader, start=2):
                counts["input"] += 1
                key = ":".join(str(row.get(field, "")) for field in KEYS[entity])
                try:
                    if None in row or any(value is None for value in row.values()):
                        raise ValueError("COLUMN_COUNT_MISMATCH")
                    values = parse_row(entity, row)
                except (ValueError, ValidationError) as error:
                    code = (
                        str(error) if isinstance(error, ValueError) else "INVALID_SOURCE_TIMESTAMP"
                    )
                    counts["rejected"] += 1
                    add_issue(report, entity, number, key, code, "ERROR")
                    continue
                canonical_key = key
                if entity in {"items", "payments"}:
                    sequence = values[
                        "source_order_item_id" if entity == "items" else "payment_sequential"
                    ]
                    canonical_key = f"{values['order__source_order_id']}:{sequence}"
                if canonical_key in seen:
                    counts["duplicate_input"] += 1
                    add_issue(report, entity, number, key, "DUPLICATE_INPUT", "ERROR")
                    continue
                seen.add(canonical_key)
                parsed[entity].append((number, key, values))
                counts["accepted"] += 1
            if counts["input"] != expected["rows"]:
                raise ValueError("ROW_COUNT_MISMATCH")
    references = {
        "customer__source_customer_id": ("customers", "source_customer_id"),
        "order__source_order_id": ("orders", "source_order_id"),
        "product__source_product_id": ("products", "source_product_id"),
        "seller__source_seller_id": ("sellers", "source_seller_id"),
    }
    for entity in ["orders", "items", "payments"]:
        parent_keys = {
            field: {r[2][column] for r in parsed[parent]}
            for field, (parent, column) in references.items()
        }
        valid = []
        for number, key, values in parsed[entity]:
            missing = [
                field
                for field in references
                if field in values and values[field] not in parent_keys[field]
            ]
            if missing:
                counts = report["files"][FILES[entity]]
                counts["accepted"] -= 1
                counts["rejected"] += 1
                add_issue(
                    report, entity, number, key, "MISSING_PARENT:" + ",".join(missing), "ERROR"
                )
            else:
                valid.append((number, key, values))
        parsed[entity] = valid
    translations = {v["source_name"]: v for _, _, v in parsed["translations"]}
    for number, key, product in parsed["products"]:
        category = product["category__source_name"]
        if category and category not in translations:
            translations[category] = {"source_name": category, "english_name": None}
        if not category:
            add_issue(report, "products", number, key, "MISSING_CATEGORY")
        elif translations[category]["english_name"] is None:
            add_issue(report, "products", number, key, "UNTRANSLATED_CATEGORY")
        if any(product[field] is None for field in PRODUCT_INTS.values()):
            add_issue(report, "products", number, key, "MISSING_PRODUCT_ATTRIBUTES")
    parsed["categories"] = [(None, key, value) for key, value in translations.items()]
    anomalies(parsed, report)
    return {entity: [values for _, _, values in parsed[entity]] for entity in MODELS}


def anomalies(parsed, report):
    item_totals, payment_totals = defaultdict(Decimal), defaultdict(Decimal)
    for _, _, item in parsed["items"]:
        item_totals[item["order__source_order_id"]] += item["price"] + item["freight_value"]
    for number, key, payment in parsed["payments"]:
        payment_totals[payment["order__source_order_id"]] += payment["payment_value"]
        if payment["payment_value"] == 0:
            add_issue(report, "payments", number, key, "ZERO_PAYMENT_VALUE")
        if payment["payment_installments"] == 0:
            add_issue(report, "payments", number, key, "ZERO_INSTALLMENTS")
        if payment["payment_type"] == "not_defined":
            add_issue(report, "payments", number, key, "UNDEFINED_PAYMENT_TYPE")
    reconciliation = Counter()
    differences = []
    total_difference = Decimal("0.00")
    maximum_difference = Decimal("0.00")
    for number, key, order in parsed["orders"]:
        if order["source_status"] not in SOURCE_STATUSES:
            add_issue(report, "orders", number, key, "UNRECOGNIZED_STATUS")
        if order["source_status"] == "delivered":
            for field in [
                "approved_at_source",
                "delivered_carrier_at_source",
                "delivered_customer_at_source",
            ]:
                if order[field] is None:
                    add_issue(report, "orders", number, key, "DELIVERED_MISSING:" + field)
        if order["source_status"] == "canceled" and order["delivered_customer_at_source"]:
            add_issue(report, "orders", number, key, "CANCELED_WITH_DELIVERY")
        chain = [
            order[name + "_source"]
            for name in [
                "purchased_at",
                "approved_at",
                "delivered_carrier_at",
                "delivered_customer_at",
            ]
        ]
        observed = [date for date in chain if date is not None]
        if any(a > b for a, b in zip(observed, observed[1:], strict=False)):
            add_issue(report, "orders", number, key, "UNEXPECTED_CHRONOLOGY")
        if key not in item_totals:
            add_issue(report, "orders", number, key, "MISSING_ITEMS")
        if key not in payment_totals:
            add_issue(report, "orders", number, key, "MISSING_PAYMENTS")
        if key in item_totals and key in payment_totals:
            delta = payment_totals[key] - item_totals[key]
            total_difference += delta
            maximum_difference = max(maximum_difference, abs(delta))
            reconciliation["comparable_orders"] += 1
            reconciliation["exact_matches"] += delta == 0
            reconciliation["difference_above_001"] += abs(delta) > Decimal("0.01")
            if abs(delta) > Decimal("0.01"):
                add_issue(report, "orders", number, key, "PAYMENT_ITEM_DIFFERENCE")
                differences.append(
                    {
                        "source_order_id": key,
                        "payment_minus_items_and_freight": format(delta, ".2f"),
                    }
                )
    report["reconciliation"] = {
        **dict(reconciliation),
        "sum_signed_difference": format(total_difference, ".2f"),
        "maximum_absolute_difference": format(maximum_difference, ".2f"),
        "differences_above_001": differences,
    }


def publish(entities, snapshot):
    references = {}
    for entity, model in MODELS.items():
        rows = []
        for values in entities[entity]:
            converted = {}
            for field, value in values.items():
                if "__" in field:
                    relation, column = field.split("__")
                    converted[relation + "_id"] = (
                        references[column][value] if value is not None else None
                    )
                else:
                    converted[field] = value
            if entity not in {"items", "payments"}:
                converted["snapshot"] = snapshot
            rows.append(model(**converted))
        model.objects.bulk_create(rows, batch_size=2000)
        column = {
            "categories": "source_name",
            "customers": "source_customer_id",
            "products": "source_product_id",
            "sellers": "source_seller_id",
            "orders": "source_order_id",
        }.get(entity)
        if column:
            references[column] = dict(model.objects.values_list(column, "pk"))


def verify_content(entities, snapshot):
    for entity, model in MODELS.items():
        fields = (
            list(entities[entity][0])
            if entities[entity]
            else [f.name for f in model._meta.fields if f.name not in {"id", "snapshot"}]
        )
        if model.objects.count() != len(entities[entity]) or content_hash(
            model.objects.values(*fields).iterator(chunk_size=2000)
        ) != content_hash(entities[entity]):
            raise ValueError("PERSISTED_CONTENT_MISMATCH:" + entity)
        if (
            entity not in {"items", "payments"}
            and model.objects.exclude(snapshot=snapshot).exists()
        ):
            raise ValueError("PERSISTED_SNAPSHOT_MISMATCH")


def import_archive(*, archive, manifest, expected_database, dry_run=False):
    started = time.monotonic()
    report = {
        "status": "FAILED",
        "mapping_version": MAPPING_VERSION,
        "files": {},
        "issues": [],
        "deferred_files": {},
        "imported": 0,
        "skipped": 0,
        "dry_run": dry_run,
        "dataset_ref": manifest.get("dataset_ref"),
        "source_url": manifest.get("source_url"),
        "reported_version": manifest.get("reported_version"),
        "license": manifest.get("license"),
        "retrieved_on": manifest.get("retrieved_on"),
        "retrieval_precision": "calendar date only",
    }
    run = None
    acquired = False
    try:
        if connection.vendor != "postgresql":
            raise ValueError("POSTGRESQL_REQUIRED")
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_user")
            database, role = cursor.fetchone()
            if database != expected_database or database in {"postgres", "template0", "template1"}:
                raise ValueError("TARGET_DATABASE_MISMATCH")
            report["target_database"] = database
            report["database_role"] = role
            cursor.execute("SELECT pg_try_advisory_lock(%s, %s)", IMPORT_LOCK)
            acquired = cursor.fetchone()[0]
            if not acquired:
                raise ValueError("IMPORT_ALREADY_RUNNING")
        if not dry_run:
            run = ImportRun.objects.create()
            report["import_run_id"] = run.pk
        entities = validate_archive(archive, manifest, report)
        report["proposed_entities"] = {key: len(rows) for key, rows in entities.items()}
        if any(issue["severity"] == "ERROR" for issue in report["issues"]):
            raise ValueError("SOURCE_VALIDATION_FAILED")
        existing = DatasetSnapshot.objects.first()
        member_manifest = {
            "files": manifest["files"],
            "content_hashes": {key: content_hash(rows) for key, rows in entities.items()},
        }
        if existing:
            if (
                existing.archive_sha256 != manifest["archive_sha256"]
                or existing.mapping_version != MAPPING_VERSION
                or existing.publication_status != "COMPLETE"
                or existing.member_manifest != member_manifest
                or existing.dataset_ref != manifest["dataset_ref"]
                or existing.source_url != manifest["source_url"]
                or existing.reported_version != manifest["reported_version"]
                or existing.license_identifier != manifest["license"]
                or existing.retrieved_at
                != datetime.fromisoformat(manifest["retrieved_on"] + "T00:00:00+00:00")
            ):
                raise ValueError("SNAPSHOT_CONFLICT")
            verify_content(entities, existing)
            report["status"] = "DRY_RUN" if dry_run else "NOOP"
            if not dry_run:
                report["skipped"] = sum(len(rows) for rows in entities.values())
                run.snapshot = existing
        else:
            if any(model.objects.exists() for model in MODELS.values()):
                raise ValueError("NONEMPTY_TARGET_WITHOUT_SNAPSHOT")
            if dry_run:
                report["status"] = "DRY_RUN"
            else:
                with transaction.atomic():
                    snapshot = DatasetSnapshot.objects.create(
                        dataset_ref=manifest["dataset_ref"],
                        source_url=manifest["source_url"],
                        reported_version=manifest["reported_version"],
                        archive_sha256=manifest["archive_sha256"],
                        member_manifest=member_manifest,
                        mapping_version=MAPPING_VERSION,
                        # A UTC day boundary encodes the available date, not an observed instant.
                        license_identifier=manifest["license"],
                        retrieved_at=datetime.fromisoformat(
                            manifest["retrieved_on"] + "T00:00:00+00:00"
                        ),
                    )
                    publish(entities, snapshot)
                    verify_content(entities, snapshot)
                    snapshot.publication_status = "COMPLETE"
                    snapshot.save(update_fields=["publication_status"])
                report["status"] = "SUCCEEDED"
                report["imported"] = sum(len(rows) for rows in entities.values())
                run.snapshot = snapshot
        for counts in report["files"].values():
            counts["imported"] = counts["accepted"] if report["status"] == "SUCCEEDED" else 0
            counts["skipped"] = counts["accepted"] if report["status"] == "NOOP" else 0
    except Exception as error:
        # Report technical codes only; database exception text can contain source rows/secrets.
        code = str(error) if isinstance(error, ValueError) else "IMPORT_OPERATION_FAILED"
        report["failure_code"] = code
        raise ImportFailure(code, report) from error
    finally:
        warnings = [issue for issue in report["issues"] if issue["severity"] == "WARNING"]
        report["inconsistent_rows"] = len(
            {(issue["file_name"], issue["source_row_number"]) for issue in warnings}
        )
        report["issue_counts"] = dict(Counter(issue["issue_code"] for issue in report["issues"]))
        report["rejected"] = sum(counts["rejected"] for counts in report["files"].values())
        report["duplicate_input"] = sum(
            counts["duplicate_input"] for counts in report["files"].values()
        )
        report["parent_failures"] = sum(
            issue["issue_code"].startswith("MISSING_PARENT:") for issue in report["issues"]
        )
        report["committed_source_rows"] = sum(
            counts["imported"] for counts in report["files"].values()
        )
        report["skipped_source_rows"] = sum(
            counts["skipped"] for counts in report["files"].values()
        )
        report["duration_seconds"] = round(time.monotonic() - started, 3)
        metadata_error = None
        report["metadata_persisted"] = False
        try:
            if run is not None:
                with transaction.atomic():
                    report["metadata_persisted"] = True
                    run.status = report["status"]
                    run.finished_at = timezone.now()
                    run.counts = {k: v for k, v in report.items() if k != "issues"}
                    run.save(update_fields=["status", "finished_at", "counts", "snapshot"])
                    ImportIssue.objects.bulk_create(
                        [ImportIssue(run=run, **issue) for issue in report["issues"]],
                        batch_size=2000,
                    )
                report["metadata_persisted"] = True
        except Exception:
            # Publication may already be committed. Never claim it rolled back because
            # persisting the attempt report failed; preserve the original data outcome.
            report["data_status"] = report["status"]
            report["metadata_persisted"] = False
            report["primary_failure_code"] = report.get("failure_code")
            report["status"] = "REPORTING_FAILED"
            report["failure_code"] = "IMPORT_METADATA_FAILED"
            metadata_error = ImportFailure("IMPORT_METADATA_FAILED", report)
        finally:
            if acquired:
                try:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_advisory_unlock(%s, %s)", IMPORT_LOCK)
                except Exception:
                    connection.close()
                    report["lock_release"] = "CONNECTION_CLOSED"
        if metadata_error is not None:
            raise metadata_error
    return report
