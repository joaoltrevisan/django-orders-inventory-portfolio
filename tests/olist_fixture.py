"""Build tiny fictional CSV archives; no real Olist observations are copied."""

import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path

from olist.importer import FILES


def key(number):
    return f"{number:032x}"


def fixture_rows():
    return {
        "customers": [
            [key(1), key(9), "00123", "Fictional City", "SP"],
            [key(2), key(9), "00001", "Other Fictional City", "RJ"],
        ],
        "products": [[key(3), "untranslated_fixture", "10", "20", "1", "100", "10", "5", "5"]],
        "sellers": [
            [key(4), "00123", "Fictional City", "SP"],
            [key(5), "00001", "Other City", "RJ"],
        ],
        "orders": [
            [
                key(6),
                key(1),
                "delivered",
                "2017-03-01 00:15:00",
                "",
                "",
                "2017-03-03 12:00:00",
                "2017-03-05 00:00:00",
            ],
            [
                key(7),
                key(2),
                "canceled",
                "2017-03-02 10:00:00",
                "",
                "",
                "2017-03-03 12:00:00",
                "2017-03-05 00:00:00",
            ],
        ],
        "items": [
            [key(6), "1", key(3), key(4), "2017-03-02 00:00:00", "10.00", "1.00"],
            [key(6), "2", key(3), key(5), "2017-03-02 00:00:00", "20.00", "2.00"],
            [key(6), "3", key(3), key(4), "2017-03-02 00:00:00", "5.00", "0.00"],
        ],
        "payments": [
            [key(6), "1", "credit_card", "2", "30.00"],
            [key(6), "2", "voucher", "1", "8.00"],
            [key(7), "1", "not_defined", "0", "0.00"],
        ],
        "translations": [["books", "books"]],
    }


def write_fixture(directory, *, mutate=None, label="fixture"):
    rows = fixture_rows()
    if mutate:
        mutate(rows)
    template = json.loads((Path(__file__).parents[1] / "olist/source-manifest.json").read_text())
    manifest = {
        "dataset_ref": "olistbr/brazilian-ecommerce",
        "source_url": "https://example.com/fictional-fixture",
        "reported_version": "fictional-test",
        "license": "CC BY-NC-SA 4.0",
        "retrieved_on": "2026-01-01",
        "mapping_version": "olist-1",
        "files": {},
    }
    archive = Path(directory) / f"{label}.zip"
    with zipfile.ZipFile(archive, "w") as output:
        for entity, filename in FILES.items():
            stream = io.StringIO(newline="")
            writer = csv.writer(stream)
            columns = template["files"][filename]["columns"]
            writer.writerow(columns)
            writer.writerows(rows[entity])
            data = stream.getvalue().encode()
            output.writestr(filename, data)
            manifest["files"][filename] = {
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "columns": columns,
                "rows": len(rows[entity]),
            }
    manifest["archive_sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
    return archive, manifest
