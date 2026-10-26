"""Generate isolated local credentials without overwriting or printing secrets."""

import os
import secrets
from pathlib import Path

SECRET_NAMES = {
    "DJANGO_SECRET_KEY",
    "POSTGRES_PASSWORD",
    "MIGRATION_DB_PASSWORD",
    "IMPORT_DB_PASSWORD",
    "APP_DB_PASSWORD",
    "TEST_DB_PASSWORD",
}


def create_env(template, destination):
    lines = template.read_text().splitlines()
    names = {line.split("=", 1)[0] for line in lines if "=" in line and not line.startswith("#")}
    if not SECRET_NAMES.issubset(names):
        raise ValueError("The environment template is missing required secret fields.")
    rendered = []
    for line in lines:
        key = line.split("=", 1)[0]
        rendered.append(f"{key}={secrets.token_urlsafe(48)}" if key in SECRET_NAMES else line)
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        handle.write("\n".join(rendered) + "\n")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    create_env(root / ".env.example", root / ".env")
    print("Created private .env without printing secrets. Existing files are never overwritten.")
