"""Private logical backup and non-destructive recovery into a separate review cluster."""

import argparse
import hashlib
import json
import os
import re
import select
import subprocess
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

from scripts.database_schema import normalized

ROOT = Path(__file__).resolve().parents[1]


def identifier(value):
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", value):
        raise ValueError("Use a simple PostgreSQL database identifier.")
    return value


def private_bundle(path):
    path = path.absolute()
    base = ROOT / ".local" / "recovery"
    if not path.resolve().is_relative_to(base.resolve()) or path.resolve() == base.resolve():
        raise ValueError("Keep private recovery bundles below .local/recovery.")
    if any(parent.is_symlink() for parent in [path, *path.parents]):
        raise ValueError("Recovery paths cannot traverse symbolic links.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.mkdir(mode=0o700)
    return path


def private_file(path):
    return os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb")


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(262144), b""):
            digest.update(block)
    return digest.hexdigest()


class Endpoint:
    def __init__(self, project, env_file):
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", project):
            raise ValueError("Use an explicit Compose project identity.")
        self.project = project
        self.environment = {k: v for k, v in os.environ.items() if not k.startswith("COMPOSE_")}
        env_file = env_file.resolve()
        if env_file.stat().st_mode & 0o077:
            raise ValueError("Use a private mode-0600 environment file.")
        for line in env_file.read_text().splitlines():
            if line and not line.startswith("#"):
                key, value = line.split("=", 1)
                if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key) or key.startswith("COMPOSE_"):
                    raise ValueError("Use literal generated environment assignments only.")
                self.environment[key] = value
        self.compose = [
            "docker",
            "compose",
            "--project-directory",
            str(ROOT),
            "-f",
            str(ROOT / "compose.yaml"),
            "-p",
            project,
            "--env-file",
            str(env_file),
        ]

    def run(self, arguments, *, data=None, output=None):
        result = subprocess.run(
            [*self.compose, *arguments],
            cwd=ROOT,
            env=self.environment,
            input=data,
            stdout=output or subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode:
            raise RuntimeError(
                "Recovery command failed; private artifacts and fresh databases are retained."
            )
        return result.stdout if output is None else None

    def inspect(self):
        container = self.run(["ps", "--quiet", "db"]).decode().strip()
        if not container or "\n" in container:
            raise RuntimeError("Start exactly one explicit review database service.")
        result = subprocess.run(
            ["docker", "inspect", container], env=self.environment, capture_output=True, check=True
        )
        details = json.loads(result.stdout)[0]
        expected = self.project + "_olist_postgres_data"
        mounts = [m for m in details["Mounts"] if m["Destination"] == "/var/lib/postgresql/data"]
        if (
            details["Config"]["Labels"].get("com.docker.compose.project") != self.project
            or len(mounts) != 1
            or mounts[0].get("Type") != "volume"
            or mounts[0].get("Name") != expected
        ):
            raise RuntimeError("Database must use its own expected nonshared named volume.")
        return container, expected

    def psql(self, database, statement, user="olist_owner"):
        return self.run(
            [
                "exec",
                "-T",
                "db",
                "psql",
                "-X",
                "-qAt",
                "-U",
                user,
                "-d",
                identifier(database),
                "-v",
                "ON_ERROR_STOP=1",
            ],
            data=statement.encode(),
        )

    def dump_schema(self, database, *, snapshot=None):
        command = [
            "exec",
            "-T",
            "db",
            "pg_dump",
            "-U",
            "olist_owner",
            "-d",
            identifier(database),
            "--schema-only",
            "--no-owner",
            "--no-privileges",
        ]
        if snapshot:
            command.extend(["--snapshot", snapshot])
        return self.run(command)

    def create_database(self, locale, report, purpose):
        database = "olist_recovery_" + uuid.uuid4().hex[:20]
        report.setdefault("new_databases", {})[database] = {"purpose": purpose, "created": False}
        self.run(
            [
                "exec",
                "-T",
                "db",
                "createdb",
                "-U",
                "postgres",
                "--template=template0",
                "--owner=olist_owner",
                "--encoding=UTF8",
                "--lc-collate=" + locale["collation"],
                "--lc-ctype=" + locale["ctype"],
                database,
            ]
        )
        report["new_databases"][database]["created"] = True
        # Generated identifiers contain only a fixed prefix and hexadecimal digits.
        self.psql(
            "postgres",
            f'REVOKE ALL ON DATABASE "{database}" FROM PUBLIC; '
            f'GRANT CONNECT ON DATABASE "{database}" TO olist_owner;',
            user="postgres",
        )
        self.psql(
            database,
            "REVOKE ALL ON SCHEMA public FROM PUBLIC; ALTER SCHEMA public OWNER TO olist_owner;",
        )
        return database


class Snapshot:
    def __init__(self, endpoint, database):
        self.endpoint, self.database = endpoint, identifier(database)

    def receive(self):
        if not select.select([self.process.stdout], [], [], 180)[0]:
            raise RuntimeError("Recovery snapshot timed out.")
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError("Recovery snapshot process stopped unexpectedly.")
        result = json.loads(line)
        if "error" in result:
            raise RuntimeError("Read-only recovery capture failed.")
        return result

    def __enter__(self):
        self.errors = tempfile.TemporaryFile()
        self.invocation = uuid.uuid4().hex
        self.name = "olist-recovery-session-" + self.invocation
        command = [
            *self.endpoint.compose,
            "run",
            "--rm",
            "--no-deps",
            "--name",
            self.name,
            "--label",
            "olist.recovery.invocation=" + self.invocation,
            "-T",
            "--entrypoint",
            "python",
            "-e",
            "PGDATABASE=" + self.database,
            "migrate",
            "-m",
            "scripts.recovery_session",
            "--expected-database",
            self.database,
        ]
        self.process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=self.endpoint.environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.errors,
        )
        try:
            self.metadata = self.receive()
            token = self.metadata.get("snapshot", "")
            if not re.fullmatch(r"[0-9A-Fa-f]+-[0-9A-Fa-f]+-[0-9]+", token):
                raise RuntimeError("Invalid exported snapshot identity.")
            return self
        except Exception:
            self.__exit__(None, None, None)
            raise

    def capture(self):
        self.process.stdin.write(b'{"action":"capture"}\n')
        self.process.stdin.flush()
        return self.receive()

    def remove_owned_helper(self):
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", "name=" + self.name, "--format", "{{.Names}}"],
            env=self.endpoint.environment,
            capture_output=True,
            check=True,
        )
        if self.name not in result.stdout.decode().splitlines():
            return
        inspected = subprocess.run(
            ["docker", "inspect", self.name],
            env=self.endpoint.environment,
            capture_output=True,
            check=True,
        )
        labels = json.loads(inspected.stdout)[0]["Config"]["Labels"]
        if (
            labels.get("olist.recovery.invocation") != self.invocation
            or labels.get("com.docker.compose.project") != self.endpoint.project
        ):
            raise RuntimeError("Refusing to remove an unowned recovery helper.")
        subprocess.run(
            ["docker", "rm", "--force", self.name],
            env=self.endpoint.environment,
            capture_output=True,
            check=True,
        )

    def __exit__(self, exception_type, *_):
        try:
            if self.process.poll() is None:
                try:
                    self.process.stdin.write(b'{"action":"finish"}\n')
                    self.process.stdin.flush()
                    self.process.stdin.close()
                    self.process.wait(timeout=15)
                except (BrokenPipeError, subprocess.TimeoutExpired):
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait(timeout=5)
        finally:
            try:
                # CLI termination alone does not prove its one-off container stopped.
                self.remove_owned_helper()
            finally:
                if not self.process.stdin.closed:
                    self.process.stdin.close()
                self.process.stdout.close()
                self.errors.close()
        if exception_type is None and self.process.returncode != 0:
            raise RuntimeError("Recovery snapshot did not finish successfully.")


def drill(source, target, database, bundle, report):
    source_identity, target_identity = source.inspect(), target.inspect()
    if (
        source.project == target.project
        or source_identity[0] == target_identity[0]
        or source_identity[1] == target_identity[1]
    ):
        raise RuntimeError("Recovery requires separate source and target database clusters.")
    source_cluster = source.psql(
        "postgres", "SELECT system_identifier FROM pg_control_system();", user="postgres"
    ).strip()
    target_cluster = target.psql(
        "postgres", "SELECT system_identifier FROM pg_control_system();", user="postgres"
    ).strip()
    if source_cluster == target_cluster:
        raise RuntimeError("Recovery requires independently initialized PostgreSQL clusters.")
    report["distinct_cluster_identifiers_verified"] = True
    report["source_project"], report["target_project"] = source.project, target.project
    report["source_database"] = database
    report["pg_dump_version"] = (
        source.run(["exec", "-T", "db", "pg_dump", "--version"]).decode().strip()
    )
    report["pg_restore_version"] = (
        target.run(["exec", "-T", "db", "pg_restore", "--version"]).decode().strip()
    )
    dump_path, schema_path = bundle / "database.dump", bundle / "schema.sql"
    with Snapshot(source, database) as snapshot:
        report["source_runtime"] = snapshot.metadata
        state = snapshot.capture()
        schema = source.dump_schema(database, snapshot=snapshot.metadata["snapshot"])
        with private_file(schema_path) as output:
            output.write(schema)
        with private_file(dump_path) as output:
            source.run(
                [
                    "exec",
                    "-T",
                    "db",
                    "pg_dump",
                    "-U",
                    "olist_owner",
                    "-d",
                    database,
                    "--format=custom",
                    "--no-owner",
                    "--no-privileges",
                    "--snapshot",
                    snapshot.metadata["snapshot"],
                ],
                output=output,
            )
    checksum = file_hash(dump_path)
    manifest = {
        "format": 1,
        "dump_sha256": checksum,
        "schema_sha256": hashlib.sha256(schema).hexdigest(),
        "source_state": state,
        "snapshot": report["source_runtime"],
        "note": (
            "Private trusted-project archive; cluster credentials/ACLs are not recovered. "
            "Sequence observations are not MVCC-consistent."
        ),
    }
    with private_file(bundle / "manifest.json") as output:
        output.write(json.dumps(manifest, indent=2).encode())
    restored = target.create_database(report["source_runtime"], report, "data")
    reference = target.create_database(report["source_runtime"], report, "schema_reference")
    report["restored_database"], report["reference_database"] = restored, reference
    if file_hash(dump_path) != checksum:
        raise RuntimeError("Backup checksum changed before restore.")
    with dump_path.open("rb") as archive:
        result = subprocess.run(
            [
                *target.compose,
                "exec",
                "-T",
                "db",
                "pg_restore",
                "-U",
                "olist_owner",
                "-d",
                restored,
                "--single-transaction",
                "--exit-on-error",
                "--no-owner",
                "--no-acl",
            ],
            cwd=ROOT,
            env=target.environment,
            stdin=archive,
            capture_output=True,
        )
    if result.returncode:
        raise RuntimeError("Archive restore failed; the new database is retained for inspection.")
    target.psql(reference, schema.decode())
    restored_schema, reference_schema = (
        normalized(target.dump_schema(restored).decode()),
        normalized(target.dump_schema(reference).decode()),
    )
    if restored_schema != reference_schema:
        raise RuntimeError("Restored DDL differs from the identically reparsed source schema.")
    with Snapshot(target, restored) as snapshot:
        recovered = snapshot.capture()
        report["target_runtime"] = snapshot.metadata
    if (
        recovered["tables"] != state["tables"]
        or recovered["migration_history"] != state["migration_history"]
    ):
        raise RuntimeError("Restored rows or migration history differ from the source snapshot.")
    access = json.loads(
        target.psql(
            restored,
            "SELECT json_build_object("
            "'api_connect',has_database_privilege('olist_api',current_database(),'CONNECT'),"
            "'importer_connect',has_database_privilege('olist_importer',current_database(),'CONNECT'),"
            "'api_schema_usage',has_schema_privilege('olist_api','public','USAGE'));",
            user="postgres",
        )
    )
    if any(access.values()):
        raise RuntimeError("Fresh restored database access did not remain restricted.")
    report["access_before_deliberate_reconfiguration"] = access
    report.update(
        {
            "tables": state["tables"],
            "migration_history": state["migration_history"],
            "sequence_safety": recovered["sequences"],
            "all_rows_match": True,
            "schema_matches_reparsed_reference": True,
            "canonical_schema_sha256": hashlib.sha256(restored_schema.encode()).hexdigest(),
            "dump_sha256": checksum,
            "dump_bytes": dump_path.stat().st_size,
            "global_credentials_or_grants_restored": False,
            "sequence_exact_equality_claimed": False,
        }
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for kind in ["source", "target"]:
        parser.add_argument("--" + kind + "-project", required=True)
        parser.add_argument("--" + kind + "-env-file", type=Path, required=True)
    parser.add_argument("--source-database", required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--allow-trusted-source", action="store_true")
    args = parser.parse_args()
    if not args.allow_trusted_source or not re.fullmatch(
        r"olist-recovery-review(?:-[a-z0-9]+)?", args.target_project
    ):
        parser.error(
            "Explicitly allow the reviewed trusted source and use a recovery-review target."
        )
    identifier(args.source_database)
    if args.report.exists():
        raise FileExistsError("Preserve previous recovery evidence.")
    source, target = (
        Endpoint(args.source_project, args.source_env_file),
        Endpoint(args.target_project, args.target_env_file),
    )
    bundle = private_bundle(args.private_output)
    report = {
        "started_at_utc": datetime.now(UTC).isoformat(),
        "passed": False,
        "private_bundle": str(bundle.relative_to(ROOT)),
        "new_databases_retained": True,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as output:
        try:
            drill(source, target, args.source_database, bundle, report)
            report["passed"] = True
        except Exception:
            report["failure"] = (
                "Recovery failed; source is unchanged and "
                "private/new-target artifacts are retained."
            )
            raise RuntimeError(report["failure"]) from None
        finally:
            report["finished_at_utc"] = datetime.now(UTC).isoformat()
            json.dump(report, output, indent=2)
            output.write("\n")
    print("Verified restored row fingerprints, migration history, schema and next-ID safety.")


if __name__ == "__main__":
    main()
