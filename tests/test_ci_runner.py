import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from scripts.create_env import SECRET_NAMES
from scripts.run_ci import cleanup, redact, snapshot, target_environment, validate_config


class CIRunnerSafetyTests(SimpleTestCase):
    project = "olist-ci-0123456789abcdef"
    image = "olist-ci-app:olist-ci-0123456789abcdef"
    workspace = Path("/tmp/ci-workspace")

    def config(self):
        return {
            "name": self.project,
            "volumes": {"olist_postgres_data": {"name": self.project + "_olist_postgres_data"}},
            "networks": {"default": {"name": self.project + "_default"}},
            "services": {
                **{
                    name: {
                        "image": self.image,
                        "build": {"context": str(self.workspace)},
                        "environment": {"PGHOST": "db", "PGPORT": "5432", "PGDATABASE": "olist_ci"},
                    }
                    for name in ["app", "migrate", "importer", "tests"]
                },
                "db": {
                    "environment": {"POSTGRES_DB": "olist_ci"},
                    "volumes": [
                        {
                            "type": "volume",
                            "source": "olist_postgres_data",
                            "target": "/var/lib/postgresql/data",
                        }
                    ],
                },
            },
        }

    def test_accepts_exclusively_owned_configuration(self):
        validate_config(self.config(), self.project, self.image, self.workspace)
        config = self.config()
        config["networks"]["default"]["ipam"] = {}
        validate_config(config, self.project, self.image, self.workspace)

    def test_rejects_shared_storage_network_and_external_connections(self):
        cases = []
        shared = self.config()
        shared["volumes"]["olist_postgres_data"]["name"] = "existing_data"
        cases.append(shared)
        external = self.config()
        external["volumes"]["olist_postgres_data"]["external"] = True
        cases.append(external)
        network = self.config()
        network["networks"]["default"]["name"] = "shared_network"
        cases.append(network)
        connection = self.config()
        connection["services"]["migrate"]["environment"]["PGHOST"] = "production.example.com"
        cases.append(connection)
        bind = self.config()
        bind["services"]["db"]["volumes"].append(
            {"type": "bind", "source": "/outside/data", "target": "/other"}
        )
        cases.append(bind)
        for key, value in [("extra_hosts", ["db=192.0.2.10"]), ("network_mode", "host")]:
            config = self.config()
            config["services"]["migrate"][key] = value
            cases.append(config)
        for config in cases:
            with self.subTest(config=config), self.assertRaises(ValueError):
                validate_config(config, self.project, self.image, self.workspace)

    def test_rejects_shared_image_or_external_build_context(self):
        for field, value in [
            ("image", "olist-case-study-app:stage6"),
            ("build", {"context": "/outside"}),
            (
                "build",
                {
                    "context": str(self.workspace),
                    "additional_contexts": {"private": "/outside/private"},
                },
            ),
            ("build", {"context": str(self.workspace), "dockerfile": "/outside/Dockerfile"}),
        ]:
            config = self.config()
            config["services"]["tests"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_config(config, self.project, self.image, self.workspace)

    def test_target_environment_replaces_inherited_target_and_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            values = {key: "temporary-" + key for key in SECRET_NAMES}
            values["PGDATABASE"] = "olist_ci"
            (workspace / ".env").write_text("\n".join(f"{k}={v}" for k, v in values.items()))
            with patch.dict(
                "os.environ",
                {
                    "COMPOSE_PROJECT_NAME": "olist-case-study",
                    "COMPOSE_FILE": "wrong.yaml",
                    "PGDATABASE": "existing",
                    "PYTHONOPTIMIZE": "1",
                },
            ):
                environment, secrets = target_environment(workspace, self.project)
            self.assertEqual(environment["COMPOSE_PROJECT_NAME"], self.project)
            self.assertEqual(environment["COMPOSE_PROFILES"], "tools")
            self.assertEqual(environment["PGDATABASE"], "olist_ci")
            self.assertEqual(environment["COMPOSE_ENV_FILES"], str(workspace / ".env"))
            self.assertNotIn("PYTHONOPTIMIZE", environment)
            self.assertEqual(set(secrets), {values[key] for key in SECRET_NAMES})

    def test_cleanup_rejects_foreign_workspace_before_any_docker_command(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            for project, workspace in [
                ("olist-case-study", str(self.workspace)),
                (self.project, "/outside"),
            ]:
                state.write_text(
                    json.dumps({"project": project, "workspace": workspace, "image": self.image})
                )
                with patch("scripts.run_ci.execute") as command, self.assertRaises(ValueError):
                    cleanup(state)
                command.assert_not_called()

    def test_snapshot_excludes_private_inputs_and_refuses_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            root.mkdir()
            destination = Path(directory) / "copy"
            destination.mkdir()
            (root / "safe.py").write_text("value = 1\n")
            (root / ".env").write_text("PRIVATE=not-for-copy\n")
            with (
                patch("scripts.run_ci.ROOT", root),
                patch(
                    "scripts.run_ci.subprocess.check_output",
                    return_value=b"safe.py\0.env\0.local/private.csv\0",
                ),
            ):
                self.assertEqual(len(snapshot(destination)), 64)
            self.assertTrue((destination / "safe.py").exists())
            self.assertFalse((destination / ".env").exists())
            (root / "link.py").symlink_to(root / "safe.py")
            with (
                patch("scripts.run_ci.ROOT", root),
                patch("scripts.run_ci.subprocess.check_output", return_value=b"link.py\0"),
                self.assertRaises(ValueError),
            ):
                snapshot(destination)

    def test_artifact_redaction_removes_configured_secret_values(self):
        self.assertEqual(
            redact("first=long-secret-value second=short", ["short", "long-secret-value"]),
            "first=[REDACTED] second=[REDACTED]",
        )
