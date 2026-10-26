import json
import subprocess
from unittest.mock import patch

from django.test import SimpleTestCase

from scripts import verify_database_roles as roles
from scripts.database_schema import normalized


class VerificationSafetyTests(SimpleTestCase):
    def test_unexpected_permission_success_rolls_back_before_failing(self):
        result = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with patch.object(roles.subprocess, "run", return_value=result) as execute:
            with self.assertRaises(RuntimeError):
                roles.denied("fixture", "olist_api", "TRUNCATE fixture;")
        self.assertEqual(execute.call_args.kwargs["input"], "BEGIN;\nTRUNCATE fixture;\nROLLBACK;")

    def test_nonempty_history_refused_before_denial_probes(self):
        def response(database, sql, user="olist_owner"):
            if "json_build_object" in sql:
                return json.dumps(
                    {
                        "user": user,
                        "superuser": False,
                        "create_role": False,
                        "create_database": user == "olist_test",
                        "owns_database": user == "olist_owner",
                        "owner_membership": user == "olist_owner",
                        "test_membership": user == "olist_test",
                    }
                )
            if "pg_tables" in sql:
                return "olist_order"
            return "1"

        with (
            patch.object(roles, "database_name", return_value="fixture"),
            patch.object(roles, "psql", side_effect=response),
            patch.object(roles, "denied") as probe,
        ):
            with self.assertRaisesRegex(RuntimeError, "empty historical domain"):
                roles.verify()
        probe.assert_not_called()

    def test_schema_normalization_keeps_constraints_and_sql_casts(self):
        source = (
            "-- dump header\n\\restrict random_token\n"
            "CREATE TABLE fixture (amount numeric CHECK (amount > 0));\n"
            "SELECT ARRAY['A'::varchar]::text[];\n\\unrestrict random_token\n"
        )
        actual = normalized(source)
        self.assertIn("CHECK (amount > 0)", actual)
        self.assertIn("ARRAY['A'::varchar]::text[]", actual)
        self.assertNotIn("random_token", actual)
