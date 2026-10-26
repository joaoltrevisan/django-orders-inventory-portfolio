"""Run the implemented Stage 2 checks and retain actual command outputs."""

import argparse
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Choose a new verification output filename.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    compose = ["docker", "compose"]
    commands = [
        [*compose, "run", "--rm", "--entrypoint", "python", "app", "-m", "pip", "check"],
        [*compose, "run", "--rm", "--entrypoint", "ruff", "app", "check", "--no-cache", "."],
        [
            *compose,
            "run",
            "--rm",
            "--entrypoint",
            "ruff",
            "app",
            "format",
            "--check",
            "--no-cache",
            ".",
        ],
        [*compose, "run", "--rm", "migrate", "check"],
        [*compose, "run", "--rm", "migrate", "makemigrations", "--check", "--dry-run"],
        [*compose, "run", "--rm", "migrate", "migrate", "--check"],
        [*compose, "run", "--rm", "tests"],
    ]
    report = {"started_at_utc": datetime.now(UTC).isoformat(), "commands": [], "passed": False}
    try:
        for command in commands:
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            report["commands"].append(
                {
                    "command": command,
                    "exit_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            )
            print(f"exit={result.returncode}: {' '.join(command)}", flush=True)
            if result.returncode:
                print(result.stdout + result.stderr, flush=True)
                raise SystemExit(result.returncode)
        output = report["commands"][-1]
        count = re.search(r"Ran (\d+) tests in ([0-9.]+)s", output["stdout"] + output["stderr"])
        if count is None:
            raise RuntimeError("The test runner did not report a completed test count.")
        report["postgresql_tests"] = int(count.group(1))
        report["test_runtime_seconds"] = float(count.group(2))
        report["passed"] = True
    finally:
        report["finished_at_utc"] = datetime.now(UTC).isoformat()
        with args.output.open("x") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")
    print(f"Completed {report['postgresql_tests']} PostgreSQL tests; all listed checks passed.")


if __name__ == "__main__":
    main()
