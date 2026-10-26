"""Publish a validated archive only into an explicitly enabled isolated database."""

import json
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from olist.importer import ImportFailure, import_archive


class Command(BaseCommand):
    help = "Validate and atomically import a locked Olist snapshot, or verify a no-op."

    def add_arguments(self, parser):
        parser.add_argument("--archive", type=Path, required=True)
        parser.add_argument("--manifest", type=Path, required=True)
        parser.add_argument("--expected-database", required=True)
        parser.add_argument("--report", type=Path, required=True)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        if os.environ.get("OLIST_IMPORT_ENABLED") != "1":
            raise CommandError("Set OLIST_IMPORT_ENABLED=1 in the isolated importer environment.")
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_user, current_database()")
            role, database = cursor.fetchone()
        if role != "olist_importer" or database != options["expected_database"]:
            raise CommandError("Use the dedicated importer role and confirmed isolated database.")
        # Reserve the output before any import writes; do not overwrite evidence.
        with options["report"].open("x", encoding="utf-8") as output:
            try:
                try:
                    manifest = json.loads(options["manifest"].read_text(encoding="utf-8"))
                    if not isinstance(manifest, dict):
                        raise ValueError("Manifest root must be an object.")
                except (OSError, UnicodeError, ValueError) as error:
                    report = {
                        "status": "FAILED",
                        "failure_code": "INVALID_MANIFEST",
                        "imported": 0,
                        "skipped": 0,
                        "rejected": 0,
                        "duplicate_input": 0,
                        "inconsistent_rows": 0,
                    }
                    json.dump(report, output, indent=2)
                    output.write("\n")
                    raise CommandError(
                        "INVALID_MANIFEST: provide a readable JSON object."
                    ) from error
                report = import_archive(
                    archive=options["archive"],
                    manifest=manifest,
                    expected_database=options["expected_database"],
                    dry_run=options["dry_run"],
                )
            except ImportFailure as error:
                json.dump(error.report, output, indent=2, ensure_ascii=False)
                output.write("\n")
                raise CommandError(error.code) from error
            json.dump(report, output, indent=2, ensure_ascii=False)
            output.write("\n")
        self.stdout.write(
            f"{report['status']}: entities imported={report['imported']}, "
            f"skipped={report['skipped']}, rejected={report['rejected']}, "
            f"duplicate input={report['duplicate_input']}, "
            f"inconsistent rows={report['inconsistent_rows']} (retained without repair)."
        )
