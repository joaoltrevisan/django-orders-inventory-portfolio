"""Release due simulated reservations using an explicitly identified administrator."""

import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from accounts.models import User
from orders.reservations import expire_due_reservations


class Command(BaseCommand):
    help = "Expire due operational reservations; never process historical Olist orders."

    def add_arguments(self, parser):
        parser.add_argument("--expected-database", required=True)
        parser.add_argument("--actor-email", required=True)
        parser.add_argument("--limit", type=int, default=100)

    def confirm_target(self, expected_database):
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_user")
            database, role = cursor.fetchone()
        if database != expected_database or role != "olist_api":
            raise CommandError("Confirm the target database and use the operational API role.")

    def handle(self, *args, **options):
        self.confirm_target(options["expected_database"])
        actor = User.objects.filter(email=options["actor_email"]).first()
        try:
            report = expire_due_reservations(actor=actor, limit=options["limit"])
        except (PermissionDenied, ValidationError, RuntimeError) as error:
            raise CommandError(
                "Use an active administrator, a limit from 1 to 1000 and no outer transaction."
            ) from error
        self.stdout.write(json.dumps(report, sort_keys=True))
        if not report["passed"]:
            raise CommandError(
                "Some reservations could not be expired; inspect the sanitized JSON report."
            )
