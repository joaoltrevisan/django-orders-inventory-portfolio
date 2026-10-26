"""Apply least-privilege grants after migrations; run as the schema owner."""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction


class Command(BaseCommand):
    help = "Configure API/importer grants for the isolated Olist database."

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_user")
            if cursor.fetchone()[0] != "olist_owner":
                raise CommandError("Run this command with the olist_owner migration credentials.")
        quote = connection.ops.quote_name
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM olist_api, olist_importer"
            )
            cursor.execute(
                "REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM olist_api, olist_importer"
            )
            # New objects fail closed: SELECT only until this command classifies them.
            cursor.execute(
                "ALTER DEFAULT PRIVILEGES FOR ROLE olist_owner IN SCHEMA public "
                "GRANT SELECT ON TABLES TO olist_api"
            )
            for table in connection.introspection.table_names():
                if table.startswith("olist_"):
                    cursor.execute(f"GRANT SELECT ON TABLE {quote(table)} TO olist_api")
                    cursor.execute(
                        f"GRANT SELECT, INSERT ON TABLE {quote(table)} TO olist_importer"
                    )
                elif table.startswith(("accounts_", "catalog_", "inventory_", "orders_", "auth_")):
                    cursor.execute(
                        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {quote(table)} TO olist_api"
                    )
                elif table in {"django_content_type", "django_migrations"}:
                    cursor.execute(f"GRANT SELECT ON TABLE {quote(table)} TO olist_api")
                    if table == "django_migrations":
                        cursor.execute(f"GRANT SELECT ON TABLE {quote(table)} TO olist_importer")
            cursor.execute("GRANT UPDATE ON olist_import_run TO olist_importer")
            cursor.execute(
                "GRANT UPDATE (publication_status) ON olist_dataset_snapshot TO olist_importer"
            )
            cursor.execute("SELECT sequencename FROM pg_sequences WHERE schemaname = 'public'")
            for (sequence,) in cursor.fetchall():
                if sequence.startswith("olist_"):
                    cursor.execute(f"GRANT USAGE ON SEQUENCE {quote(sequence)} TO olist_importer")
                elif sequence.startswith(
                    ("accounts_", "catalog_", "inventory_", "orders_", "auth_")
                ):
                    cursor.execute(f"GRANT USAGE ON SEQUENCE {quote(sequence)} TO olist_api")
        self.stdout.write("Configured historical read-only API access and scoped importer grants.")
