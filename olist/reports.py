"""Fixed, parameterized historical SQL; never combine operational simulation facts."""

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import connection
from django.http import Http404

from .importer import MODELS, content_hash
from .models import DatasetSnapshot

SQL_ROOT = Path(__file__).resolve().parents[1] / "sql/olist"
REPORTS = (
    "order_details",
    "customer_coverage",
    "best_selling_products",
    "monthly_sales",
    "repeat_customers",
    "repeat_customer_rate",
    "running_monthly_totals",
    "category_seller_sales",
    "customer_spending",
    "delivery_performance",
    "seller_delivery",
    "reconciliation",
)
DEFAULT_START = "2016-09-01 00:00:00"
DEFAULT_END = "2018-11-01 00:00:00"


def parameters(*, start=DEFAULT_START, end=DEFAULT_END, min_units=10, min_orders=2):
    parsed = {}
    for key, value in [("start", start), ("end", end)]:
        if isinstance(value, str):
            try:
                value = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            except ValueError as error:
                raise ValidationError(
                    {key: ["Use YYYY-MM-DD HH:MM:SS without a time zone."]}
                ) from error
        if not isinstance(value, datetime) or value.utcoffset() is not None or value.microsecond:
            raise ValidationError({key: ["Use a timezone-free whole-second source timestamp."]})
        parsed[key] = value
    if parsed["start"] >= parsed["end"] or (parsed["end"] - parsed["start"]).days > 3660:
        raise ValidationError("Use an increasing interval of at most ten years.")
    for key, value, minimum in [("min_units", min_units, 1), ("min_orders", min_orders, 2)]:
        if type(value) is not int or not minimum <= value <= 1_000_000:
            raise ValidationError({key: [f"Use an integer from {minimum} to 1000000."]})
        parsed[key] = value
    return parsed


def sql_for(name):
    if name not in REPORTS:
        raise Http404("Historical report not found.")
    return (SQL_ROOT / f"{name}.sql").read_text().strip().removesuffix(";")


def execute_report(name, params, *, limit=None, offset=0):
    sql = sql_for(name)
    if limit is not None:
        sql += " LIMIT %(page_limit)s OFFSET %(page_offset)s"
        params = {**params, "page_limit": limit, "page_offset": offset}
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        columns = [field[0] for field in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def count_report(name, params):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM ({sql_for(name)}) AS historical_report", params)
        return cursor.fetchone()[0]


def serializable(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    raise TypeError("Unsupported report value.")


def ordered_result_hash(rows):
    return hashlib.sha256(
        json.dumps(rows, sort_keys=True, ensure_ascii=False, default=serializable).encode()
    ).hexdigest()


def fingerprint_dataset():
    """Recompute every mapped field/relationship using the importer's canonical hashing."""
    snapshot = DatasetSnapshot.objects.get(publication_status="COMPLETE")
    keys = {
        "Category": "source_name",
        "HistoricalCustomer": "source_customer_id",
        "HistoricalProduct": "source_product_id",
        "HistoricalSeller": "source_seller_id",
        "HistoricalOrder": "source_order_id",
    }
    fingerprints = {}
    counts = {}
    for entity, model in MODELS.items():
        fields = []
        for field in model._meta.concrete_fields:
            if field.name in {"id", "snapshot"}:
                continue
            fields.append(
                field.name + "__" + keys[field.related_model.__name__]
                if field.is_relation
                else field.name
            )
        fingerprints[entity] = content_hash(model.objects.values(*fields).iterator(chunk_size=2000))
        counts[entity] = model.objects.count()
    if fingerprints != snapshot.member_manifest["content_hashes"]:
        raise ValueError("Persisted historical content differs from the accepted source snapshot.")
    return {
        "dataset_ref": snapshot.dataset_ref,
        "source_url": snapshot.source_url,
        "reported_version": snapshot.reported_version,
        "license": snapshot.license_identifier,
        "retrieved_on": snapshot.retrieved_at.date().isoformat(),
        "retrieval_precision": (
            "Calendar date only; stored timestamp is a conventional UTC day boundary."
        ),
        "archive_sha256": snapshot.archive_sha256,
        "mapping_version": snapshot.mapping_version,
        "counts": counts,
        "content_hashes": fingerprints,
    }
