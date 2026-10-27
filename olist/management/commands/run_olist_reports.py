"""Execute the SQL collection and preserve real results, samples and ordered hashes."""

import hashlib
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from olist.reports import (
    REPORTS,
    execute_report,
    fingerprint_dataset,
    ordered_result_hash,
    parameters,
    serializable,
    sql_for,
)


class Command(BaseCommand):
    help = "Execute historical SQL reports without operational simulation data."

    def add_arguments(self, parser):
        parser.add_argument("--expected-database", required=True)
        parser.add_argument("--output", type=Path, required=True)
        parser.add_argument("--start", default="2016-09-01 00:00:00")
        parser.add_argument("--end", default="2018-11-01 00:00:00")

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_user, version()")
            database, role, version = cursor.fetchone()
        if database != options["expected_database"]:
            raise CommandError("The report target differs from the expected database.")
        params = parameters(start=options["start"], end=options["end"])
        with options["output"].open("x") as output:
            report = {
                "database": database,
                "role": role,
                "postgresql": version,
                "parameters": params,
                "dataset": fingerprint_dataset(),
                "reports": {},
            }
            for name in REPORTS:
                rows = execute_report(name, params)
                report["reports"][name] = {
                    "row_count": len(rows),
                    "ordered_result_sha256": ordered_result_hash(rows),
                    "sql_sha256": hashlib.sha256(sql_for(name).encode()).hexdigest(),
                    "rows": rows if len(rows) <= 100 else rows[:10],
                    "rows_are_sampled": len(rows) > 100,
                }
            json.dump(report, output, indent=2, default=serializable)
            output.write("\n")
        self.stdout.write(
            f"Executed {len(REPORTS)} historical SQL reports; "
            "full counts/hashes and bounded result samples retained."
        )
