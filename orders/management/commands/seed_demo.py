import json
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from orders.demo import seed_demo


class Command(BaseCommand):
    help = "Create fictional operational demo data only in an empty isolated demo database."

    def add_arguments(self, parser):
        parser.add_argument("--expected-database", required=True)
        parser.add_argument("--report", type=Path, required=True)

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(),current_user")
            database, role = cursor.fetchone()
        if (
            os.environ.get("DEMO_SEED_ENABLED") != "1"
            or database != "olist_demo"
            or options["expected_database"] != database
            or role != "olist_owner"
        ):
            raise CommandError(
                "Enable seeding explicitly in the isolated olist_demo database "
                "with owner credentials."
            )
        with options["report"].open("x") as handle:
            try:
                report = seed_demo(
                    expected_database=database, password=os.environ.get("DEMO_PASSWORD", "")
                )
            except Exception as error:
                json.dump({"status": "FAILED", "failure_code": "DEMO_SEED_REFUSED"}, handle)
                raise CommandError(
                    "Demo seed failed or refused; existing data was not replaced."
                ) from error
            json.dump(report, handle, indent=2)
            handle.write("\n")
        self.stdout.write(
            "Created fictional demo data through transactional services; "
            "no real charges or historical imports."
        )
