import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from scripts.verify_curl import ROOT, configuration, confirmed_url


class CurlSafetyTests(SimpleTestCase):
    def test_mismatched_result_still_fails_under_optimized_python(self):
        result = subprocess.run(
            [
                sys.executable,
                "-O",
                "-c",
                "from scripts.verify_curl import require; require(False, 'Expected mismatch.')",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Expected mismatch.", result.stderr)

    def test_primary_or_historical_database_refused_before_port_discovery(self):
        for values in [
            ["olist_case_study", "olist_api", 0, 4, 5, 3, 10],
            ["olist_demo", "olist_owner", 0, 4, 5, 3, 10],
            ["olist_demo", "olist_api", 1, 4, 5, 3, 10],
        ]:
            with (
                self.subTest(values=values),
                patch(
                    "scripts.verify_curl.compose_output", return_value=json.dumps(values)
                ) as command,
            ):
                with self.assertRaises(ValueError):
                    confirmed_url(["docker", "compose"])
                self.assertEqual(command.call_count, 1)

    def test_previous_workflow_data_refused_without_reset(self):
        with patch(
            "scripts.verify_curl.compose_output",
            return_value=json.dumps(["olist_demo", "olist_api", 0, 5, 7, 5, 18]),
        ) as command:
            with self.assertRaisesRegex(ValueError, "never reset"):
                confirmed_url(["docker", "compose"])
            self.assertEqual(command.call_count, 1)

    def test_only_single_loopback_port_is_accepted(self):
        for address in ["0.0.0.0:18022", "example.com:18022", "127.0.0.1:18022\n0.0.0.0:1"]:
            with (
                self.subTest(address=address),
                patch(
                    "scripts.verify_curl.compose_output",
                    side_effect=[json.dumps(["olist_demo", "olist_api", 0, 4, 5, 3, 10]), address],
                ),
                self.assertRaises(ValueError),
            ):
                confirmed_url(["docker", "compose"])
        with patch(
            "scripts.verify_curl.compose_output",
            side_effect=[
                json.dumps(["olist_demo", "olist_api", 0, 4, 5, 3, 10]),
                "127.0.0.1:18023",
            ],
        ):
            self.assertEqual(confirmed_url(["docker", "compose"]), "http://127.0.0.1:18023")

    def test_configuration_is_data_and_requires_private_demo_password(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "demo.env"
            path.write_text("PGDATABASE=olist_case_study\nDEMO_PASSWORD=short\n")
            with self.assertRaises(ValueError):
                configuration(path)
            path.write_text(
                "PGDATABASE=olist_demo\nDEMO_PASSWORD=" + "x" * 30 + "\nEXTRA=$(false)\n"
            )
            self.assertEqual(configuration(path)["EXTRA"], "$(false)")
