"""Run PostgreSQL verification in an exclusively owned disposable Compose workspace."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from scripts.create_env import SECRET_NAMES, create_env

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ("checks.json", "roles.json", "openapi.json", "schema.json", "runtime.json")


def validate_config(config, project, image, workspace):
    """Reject shared/external resources before provisioning or removing anything."""
    if (
        not re.fullmatch(r"olist-ci-[0-9a-f]{16}", project)
        or config.get("name") != project
        or image != "olist-ci-app:" + project
    ):
        raise ValueError("The CI project identity differs from its exclusive allocation.")
    volumes = config.get("volumes", {})
    if set(config.get("services", {})) != {"db", "app", "migrate", "importer", "tests"}:
        raise ValueError("CI requires the explicit complete service profile.")
    if set(volumes) != {"olist_postgres_data"} or volumes["olist_postgres_data"] != {
        "name": project + "_olist_postgres_data"
    }:
        raise ValueError("CI may use only its own nonexternal database volume.")
    networks = config.get("networks", {})
    default = networks.get("default", {})
    if (
        set(networks) != {"default"}
        or set(default) - {"name", "ipam", "external"}
        or default.get("name") != project + "_default"
        or default.get("external", False)
        or default.get("ipam", {}) != {}
    ):
        raise ValueError("CI may use only its own default network.")
    for name in ["app", "migrate", "importer", "tests"]:
        service = config["services"][name]
        if service["image"] != image:
            raise ValueError("All CI application services must use the exclusive image tag.")
        if Path(service["build"]["context"]).resolve() != workspace.resolve():
            raise ValueError("CI image builds must stay inside the copied workspace.")
        build = service["build"]
        if set(build) - {"context", "dockerfile"}:
            raise ValueError("CI does not permit additional build inputs or build options.")
        dockerfile = workspace / build.get("dockerfile", "Dockerfile")
        if not dockerfile.resolve().is_relative_to(workspace.resolve()):
            raise ValueError("The CI Dockerfile must remain inside its copied workspace.")
        values = service["environment"]
        if (values["PGHOST"], str(values["PGPORT"]), values["PGDATABASE"]) != (
            "db",
            "5432",
            "olist_ci",
        ):
            raise ValueError("CI connections must target the private disposable database.")
    database = config["services"]["db"]
    if database.get("ports") or database["environment"]["POSTGRES_DB"] != "olist_ci":
        raise ValueError("The disposable database must remain private and explicitly named.")
    if not any(
        mount.get("type") == "volume"
        and mount.get("source") == "olist_postgres_data"
        and mount.get("target") == "/var/lib/postgresql/data"
        for mount in database["volumes"]
    ):
        raise ValueError("Database storage must use the owned disposable volume.")
    for name, service in config["services"].items():
        if any(
            key in service
            for key in [
                "network_mode",
                "extra_hosts",
                "dns",
                "dns_search",
                "dns_opt",
                "external_links",
                "links",
                "volumes_from",
                "pid",
                "ipc",
                "devices",
            ]
        ):
            raise ValueError(
                "CI does not permit host aliases, shared namespaces or external mounts."
            )
        if service.get("privileged"):
            raise ValueError("CI services may not use privileged containers.")
        networks = service.get("networks", {"default": None})
        if set(networks) != {"default"} or networks["default"] not in (None, {}):
            raise ValueError("CI services must use only the unmodified private default network.")
        for mount in service.get("volumes", []):
            if mount["type"] == "bind":
                if not Path(mount["source"]).resolve().is_relative_to(workspace.resolve()):
                    raise ValueError("CI bind mounts must stay inside the copied workspace.")
            elif not (
                name == "db"
                and mount["type"] == "volume"
                and mount["source"] == "olist_postgres_data"
            ):
                raise ValueError("CI may not mount shared or anonymous storage.")


def target_environment(workspace, project):
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("COMPOSE_")
    }
    # Neither exported local credentials nor optimization may override this disposable target.
    environment.pop("PYTHONOPTIMIZE", None)
    values = {}
    for line in (workspace / ".env").read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    environment.update(values)
    environment.update(
        {
            "COMPOSE_PROJECT_NAME": project,
            "COMPOSE_PROFILES": "tools",
            "COMPOSE_FILE": os.pathsep.join(
                str(workspace / name) for name in ["compose.yaml", "compose.ci.yaml"]
            ),
            "COMPOSE_ENV_FILES": str(workspace / ".env"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    return environment, [values[key] for key in SECRET_NAMES]


def redact(text, secrets):
    for secret in sorted(secrets, key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    return text


def snapshot(workspace):
    """Copy tracked working-tree files, excluding credentials and local inputs."""
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    digest = hashlib.sha256()
    for name in sorted(filter(None, names)):
        relative = Path(name)
        if relative.parts[0] in {".local", "ci-results"} or (
            relative.name.startswith(".env") and relative.name != ".env.example"
        ):
            continue
        source = ROOT / relative
        if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(ROOT):
            raise ValueError("CI requires regular tracked files inside the repository.")
        destination = workspace / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        if relative.parts[0] not in {"docs", "reports"}:
            digest.update(name.encode() + b"\0" + source.read_bytes())
    return digest.hexdigest()


def execute(command, workspace, environment):
    return subprocess.run(command, cwd=workspace, env=environment, capture_output=True, text=True)


def resolved_config(workspace, environment, project, image):
    result = execute(["docker", "compose", "config", "--format", "json"], workspace, environment)
    if result.returncode:
        raise RuntimeError("The private CI Compose configuration could not be resolved.")
    validate_config(json.loads(result.stdout), project, image, workspace)


def cleanup(state_path):
    if not state_path.exists():
        return
    state = json.loads(state_path.read_text())
    if state.get("cleanup_complete"):
        return
    project = state["project"]
    workspace = Path(state["workspace"])
    if (
        not re.fullmatch(r"olist-ci-[0-9a-f]{16}", project)
        or state["image"] != "olist-ci-app:" + project
        or workspace != ROOT / ".local/ci-workspaces" / project
        or workspace.is_symlink()
        or json.loads((workspace / ".ci-owner.json").read_text()) != {"project": project}
    ):
        raise ValueError("Refusing cleanup outside the allocated CI workspace.")
    environment, secrets = target_environment(workspace, project)
    resolved_config(workspace, environment, project, state["image"])
    result = execute(
        ["docker", "compose", "down", "--volumes", "--remove-orphans"], workspace, environment
    )
    state["cleanup_exit_code"] = result.returncode
    state["cleanup_output"] = redact(result.stdout + result.stderr, secrets)
    if result.returncode:
        state_path.write_text(json.dumps(state, indent=2) + "\n")
        raise RuntimeError("CI cleanup failed; retry the guarded cleanup with its state file.")
    # Remove only this tag, never an image ID or another project's image.
    existing = execute(["docker", "image", "ls", "--quiet", state["image"]], workspace, environment)
    if existing.returncode:
        raise RuntimeError("CI could not verify its image cleanup state.")
    if existing.stdout.strip():
        result = execute(["docker", "image", "rm", state["image"]], workspace, environment)
        if result.returncode:
            raise RuntimeError("CI could not remove its exclusive image tag.")
    state["image_cleanup_exit_code"] = 0
    state["cleanup_complete"] = True
    shutil.rmtree(workspace)
    state_path.write_text(json.dumps(state, indent=2) + "\n")


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    project = "olist-ci-" + uuid.uuid4().hex[:16]
    image = "olist-ci-app:" + project
    workspace = ROOT / ".local/ci-workspaces" / project
    workspace.parent.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(mode=0o700)
    state_path = output / "cleanup-state.json"
    summary = {
        "started_at_utc": datetime.now(UTC).isoformat(),
        "passed": False,
        "project": project,
        "commands": [],
    }
    secrets = []
    try:
        summary["source_inputs_sha256"] = snapshot(workspace)
        template = workspace / ".ci.env.template"
        template.write_text(
            (workspace / ".env.example")
            .read_text()
            .replace("PGDATABASE=olist_case_study", "PGDATABASE=olist_ci")
        )
        create_env(template, workspace / ".env")
        template.unlink()
        (workspace / ".ci-owner.json").write_text(json.dumps({"project": project}))
        override = {
            "services": {name: {"image": image} for name in ["app", "migrate", "importer", "tests"]}
        }
        (workspace / "compose.ci.yaml").write_text(json.dumps(override))
        for directory in [".local/analysis-reports", ".local/import-reports", "evidence"]:
            (workspace / directory).mkdir(parents=True, exist_ok=True)
        environment, secrets = target_environment(workspace, project)
        resolved_config(workspace, environment, project, image)
        for command in [
            ["docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=" + project],
            [
                "docker",
                "volume",
                "ls",
                "-q",
                "--filter",
                "label=com.docker.compose.project=" + project,
            ],
            [
                "docker",
                "network",
                "ls",
                "-q",
                "--filter",
                "label=com.docker.compose.project=" + project,
            ],
            ["docker", "image", "ls", "--quiet", image],
        ]:
            result = execute(command, workspace, environment)
            if result.returncode or result.stdout.strip():
                raise RuntimeError("Refusing an existing or unverifiable CI allocation.")
        state_path.write_text(
            json.dumps(
                {
                    "project": project,
                    "image": image,
                    "workspace": str(workspace),
                    "cleanup_complete": False,
                },
                indent=2,
            )
            + "\n"
        )
        evidence = workspace / "evidence"
        python = sys.executable
        compose = ["docker", "compose"]
        commands = [
            ("build", [*compose, "build", "app"], None),
            ("database", [*compose, "up", "-d", "--wait", "db"], None),
            ("migrate", [*compose, "run", "--rm", "migrate"], None),
            ("grants", [*compose, "run", "--rm", "migrate", "configure_database_roles"], None),
            (
                "checks",
                [python, "scripts/verify_stage2.py", "--output", str(evidence / "checks.json")],
                None,
            ),
            (
                "roles",
                [
                    python,
                    "scripts/verify_database_roles.py",
                    "--report",
                    str(evidence / "roles.json"),
                ],
                None,
            ),
            (
                "openapi",
                [
                    *compose,
                    "run",
                    "--rm",
                    "migrate",
                    "spectacular",
                    "--format",
                    "openapi-json",
                    "--validate",
                    "--fail-on-warn",
                ],
                "openapi.json",
            ),
            (
                "schema",
                [
                    python,
                    "scripts/database_schema.py",
                    "verify",
                    "--report",
                    str(evidence / "schema.json"),
                ],
                None,
            ),
            (
                "runtime",
                [
                    *compose,
                    "run",
                    "--rm",
                    "--entrypoint",
                    "python",
                    "migrate",
                    "-m",
                    "scripts.runtime_versions",
                ],
                "runtime.json",
            ),
        ]
        for label, command, stdout_file in commands:
            result = execute(command, workspace, environment)
            summary["commands"].append(
                {
                    "name": label,
                    "command": command,
                    "exit_code": result.returncode,
                    "stdout": redact(result.stdout, secrets),
                    "stderr": redact(result.stderr, secrets),
                }
            )
            print(f"{label}: exit={result.returncode}", flush=True)
            if stdout_file and result.returncode == 0:
                json.loads(result.stdout)
                (evidence / stdout_file).write_text(result.stdout)
            for name in ARTIFACTS:
                source = evidence / name
                if source.exists():
                    (output / name).write_text(redact(source.read_text(), secrets))
            if result.returncode:
                raise RuntimeError(
                    f"CI verification failed during {label}; inspect sanitized evidence."
                )
        summary["passed"] = True
    except Exception as error:
        summary["failure"] = redact(str(error), secrets)
        raise
    finally:
        try:
            if state_path.exists():
                cleanup(state_path)
            elif workspace.exists():
                shutil.rmtree(workspace)
        except Exception as error:
            summary["passed"] = False
            summary["cleanup_failure"] = redact(str(error), secrets)
            raise
        finally:
            summary["finished_at_utc"] = datetime.now(UTC).isoformat()
            (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--output", type=Path)
    target.add_argument("--cleanup", type=Path)
    args = parser.parse_args()
    if args.cleanup:
        cleanup(args.cleanup.resolve())
    else:
        run(args.output.resolve())


if __name__ == "__main__":
    main()
