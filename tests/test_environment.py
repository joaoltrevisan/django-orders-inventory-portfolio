import tempfile
from pathlib import Path
from unittest.mock import patch

from django.db import DatabaseError
from django.test import SimpleTestCase, TestCase

from scripts.create_env import SECRET_NAMES, create_env


class EnvironmentFileTests(SimpleTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.template = self.root / "example"
        self.template.write_text("\n".join(f"{key}=placeholder" for key in sorted(SECRET_NAMES)))
        self.destination = self.root / "local.env"

    def test_generated_secrets_are_distinct_private_and_template_is_preserved(self):
        original = self.template.read_bytes()
        create_env(self.template, self.destination)
        values = [line.split("=", 1)[1] for line in self.destination.read_text().splitlines()]
        self.assertEqual(len(set(values)), len(SECRET_NAMES))
        self.assertTrue(all(len(value) >= 48 for value in values))
        self.assertEqual(self.destination.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.template.read_bytes(), original)

    def test_existing_configuration_is_not_overwritten(self):
        self.destination.write_text("preserve-existing-configuration")
        with self.assertRaises(FileExistsError):
            create_env(self.template, self.destination)
        self.assertEqual(self.destination.read_text(), "preserve-existing-configuration")

    def test_invalid_template_does_not_create_a_partial_file(self):
        self.template.write_text("DJANGO_SECRET_KEY=\n")
        with self.assertRaises(ValueError):
            create_env(self.template, self.destination)
        self.assertFalse(self.destination.exists())


class HealthTests(TestCase):
    def test_health_probes_real_postgresql(self):
        response = self.client.get("/health/", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_database_failure_is_sanitized(self):
        with patch("config.views.connection.cursor", side_effect=DatabaseError("private detail")):
            response = self.client.get("/health/", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})

    def test_unimplemented_api_has_english_not_found_response(self):
        response = self.client.get("/api/not-implemented/", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Resource not found.")
