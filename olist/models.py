"""Historical source facts, never operational accounts, offers, or payments."""

from django.db import models

from common.fields import StrictIntegerField
from common.limits import MAX_ORDER_TOTAL

from .fields import SourceDateTimeField

SOURCE_ID = r"^[0-9a-f]{32}$"
SHA256 = r"^[0-9a-f]{64}$"


class DatasetSnapshot(models.Model):
    singleton = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    dataset_ref = models.CharField(max_length=200)
    source_url = models.URLField()
    reported_version = models.CharField(max_length=100)
    archive_sha256 = models.CharField(max_length=64, unique=True)
    member_manifest = models.JSONField()
    mapping_version = models.CharField(max_length=50)
    license_identifier = models.CharField(max_length=50, default="CC BY-NC-SA 4.0")
    publication_status = models.CharField(max_length=20, default="PENDING")
    retrieved_at = models.DateTimeField()

    class Meta:
        db_table = "olist_dataset_snapshot"
        constraints = [
            models.CheckConstraint(condition=models.Q(singleton=1), name="snapshot_singleton_one"),
            models.CheckConstraint(
                condition=models.Q(archive_sha256__regex=SHA256), name="snapshot_hash_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(publication_status__in=["PENDING", "COMPLETE"]),
                name="snapshot_status_valid",
            ),
        ]


class ImportRun(models.Model):
    snapshot = models.ForeignKey(DatasetSnapshot, null=True, blank=True, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, default="RUNNING")
    counts = models.JSONField(default=dict)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "olist_import_run"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["RUNNING", "SUCCEEDED", "FAILED", "NOOP"]),
                name="import_run_status_valid",
            ),
        ]


class ImportIssue(models.Model):
    run = models.ForeignKey(ImportRun, on_delete=models.PROTECT, related_name="issues")
    file_name = models.CharField(max_length=200)
    source_row_number = StrictIntegerField(null=True, blank=True)
    source_key = models.CharField(max_length=200, blank=True)
    issue_code = models.CharField(max_length=100)
    severity = models.CharField(max_length=10)

    class Meta:
        db_table = "olist_import_issue"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(severity__in=["ERROR", "WARNING"]),
                name="import_issue_severity_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(source_row_number__isnull=True)
                | models.Q(source_row_number__gte=1),
                name="import_issue_row_positive",
            ),
        ]


class HistoricalCustomer(models.Model):
    data_origin = "OLIST_HISTORICAL"
    snapshot = models.ForeignKey(DatasetSnapshot, on_delete=models.PROTECT)
    source_customer_id = models.CharField(max_length=32, unique=True)
    customer_unique_id = models.CharField(max_length=32, db_index=True)
    zip_code_prefix = models.CharField(max_length=5)
    city = models.CharField(max_length=200)
    state = models.CharField(max_length=2)

    class Meta:
        db_table = "olist_customer"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(source_customer_id__regex=SOURCE_ID)
                & models.Q(customer_unique_id__regex=SOURCE_ID),
                name="historical_customer_ids_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(zip_code_prefix__regex=r"^[0-9]{5}$"),
                name="historical_customer_zip_valid",
            ),
        ]


class Category(models.Model):
    snapshot = models.ForeignKey(DatasetSnapshot, on_delete=models.PROTECT)
    source_name = models.CharField(max_length=200, unique=True)
    english_name = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        db_table = "olist_category"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(source_name__regex=r"\S"), name="historical_category_required"
            ),
        ]


class HistoricalProduct(models.Model):
    data_origin = "OLIST_HISTORICAL"
    snapshot = models.ForeignKey(DatasetSnapshot, on_delete=models.PROTECT)
    source_product_id = models.CharField(max_length=32, unique=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, null=True, blank=True)
    name_length = models.PositiveIntegerField(null=True, blank=True)
    description_length = models.PositiveIntegerField(null=True, blank=True)
    photos_count = models.PositiveIntegerField(null=True, blank=True)
    weight_g = models.PositiveIntegerField(null=True, blank=True)
    length_cm = models.PositiveIntegerField(null=True, blank=True)
    height_cm = models.PositiveIntegerField(null=True, blank=True)
    width_cm = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = "olist_product"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(source_product_id__regex=SOURCE_ID),
                name="historical_product_id_valid",
            ),
        ]


class HistoricalSeller(models.Model):
    data_origin = "OLIST_HISTORICAL"
    snapshot = models.ForeignKey(DatasetSnapshot, on_delete=models.PROTECT)
    source_seller_id = models.CharField(max_length=32, unique=True)
    zip_code_prefix = models.CharField(max_length=5)
    city = models.CharField(max_length=200)
    state = models.CharField(max_length=2)

    class Meta:
        db_table = "olist_seller"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(source_seller_id__regex=SOURCE_ID),
                name="historical_seller_id_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(zip_code_prefix__regex=r"^[0-9]{5}$"),
                name="historical_seller_zip_valid",
            ),
        ]


class HistoricalOrder(models.Model):
    data_origin = "OLIST_HISTORICAL"
    snapshot = models.ForeignKey(DatasetSnapshot, on_delete=models.PROTECT)
    source_order_id = models.CharField(max_length=32, unique=True)
    customer = models.ForeignKey(
        HistoricalCustomer, on_delete=models.PROTECT, related_name="orders"
    )
    source_status = models.CharField(max_length=50)
    purchased_at_raw = models.CharField(max_length=19)
    purchased_at_source = SourceDateTimeField()
    approved_at_raw = models.CharField(max_length=19, blank=True)
    approved_at_source = SourceDateTimeField(null=True, blank=True)
    delivered_carrier_at_raw = models.CharField(max_length=19, blank=True)
    delivered_carrier_at_source = SourceDateTimeField(null=True, blank=True)
    delivered_customer_at_raw = models.CharField(max_length=19, blank=True)
    delivered_customer_at_source = SourceDateTimeField(null=True, blank=True)
    estimated_delivery_at_raw = models.CharField(max_length=19, blank=True)
    estimated_delivery_at_source = SourceDateTimeField(null=True, blank=True)

    class Meta:
        db_table = "olist_order"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(source_order_id__regex=SOURCE_ID),
                name="historical_order_id_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(source_status__regex=r"\S"), name="historical_status_required"
            ),
        ]


class HistoricalOrderItem(models.Model):
    data_origin = "OLIST_HISTORICAL"
    order = models.ForeignKey(HistoricalOrder, on_delete=models.PROTECT, related_name="items")
    source_order_item_id = StrictIntegerField()
    product = models.ForeignKey(HistoricalProduct, on_delete=models.PROTECT, related_name="items")
    seller = models.ForeignKey(HistoricalSeller, on_delete=models.PROTECT, related_name="items")
    price = models.DecimalField(max_digits=16, decimal_places=2)
    freight_value = models.DecimalField(max_digits=16, decimal_places=2)
    shipping_limit_at_raw = models.CharField(max_length=19)
    shipping_limit_at_source = SourceDateTimeField()

    class Meta:
        db_table = "olist_order_item"
        constraints = [
            models.UniqueConstraint(
                fields=["order", "source_order_item_id"], name="historical_item_line_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(source_order_item_id__gt=0), name="historical_item_line_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(
                    price__gte=0,
                    price__lte=MAX_ORDER_TOTAL,
                    freight_value__gte=0,
                    freight_value__lte=MAX_ORDER_TOTAL,
                ),
                name="historical_item_amounts_finite",
            ),
        ]


class HistoricalPaymentRecord(models.Model):
    data_origin = "OLIST_HISTORICAL"
    order = models.ForeignKey(
        HistoricalOrder, on_delete=models.PROTECT, related_name="payment_records"
    )
    payment_sequential = StrictIntegerField()
    payment_type = models.CharField(max_length=50)
    payment_installments = StrictIntegerField()
    payment_value = models.DecimalField(max_digits=16, decimal_places=2)

    class Meta:
        db_table = "olist_payment_record"
        constraints = [
            models.UniqueConstraint(
                fields=["order", "payment_sequential"], name="historical_payment_sequence_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(payment_sequential__gt=0, payment_installments__gte=0),
                name="historical_payment_counts_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(payment_value__gte=0, payment_value__lte=MAX_ORDER_TOTAL),
                name="historical_payment_amount_finite",
            ),
        ]
