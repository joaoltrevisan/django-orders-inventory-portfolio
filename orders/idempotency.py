"""Creation-key identity and transaction-scoped serialization for simulated orders."""

import hashlib
import json
import re

from django.core.exceptions import ValidationError
from django.db import connection


def key_hash(value):
    if value is None:
        return None
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", value) is None:
        raise ValidationError(
            {"Idempotency-Key": ["Use 1 to 128 ASCII letters, digits, '.', '_', ':' or '-'."]}
        )
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def request_fingerprint(items, address):
    payload = {
        "version": 1,
        "items": sorted(items, key=lambda item: item["offer_id"]),
        "shipping_address": address,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def lock_creation_key(customer_id, digest):
    if not connection.in_atomic_block:
        raise RuntimeError("Creation-key locking requires an active transaction.")
    identity = f"order-create:v1:{customer_id}:{digest}".encode("ascii")
    lock_id = int.from_bytes(hashlib.sha256(identity).digest()[:8], "big", signed=True)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_id])
