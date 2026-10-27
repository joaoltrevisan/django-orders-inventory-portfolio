"""Create separate benchmark/demo credentials without modifying the application .env."""

import argparse
import secrets
import tempfile
from pathlib import Path

if __package__:
    from .create_env import create_env
else:
    from create_env import create_env

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["benchmark", "demo"])
    args = parser.parse_args()
    directory = ROOT / ".local/analysis"
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{args.kind}.env"
    template = (
        (ROOT / ".env.example")
        .read_text()
        .replace("PGDATABASE=olist_case_study", f"PGDATABASE=olist_{args.kind}")
        .replace("APP_PORT=18020", f"APP_PORT={18021 if args.kind == 'benchmark' else 18022}")
    )
    if args.kind == "demo":
        template += f"\nDEMO_PASSWORD={secrets.token_urlsafe(36)}\n"
    with tempfile.TemporaryDirectory() as temporary:
        source = Path(temporary) / "template"
        source.write_text(template)
        create_env(source, destination)
    print(
        f"Created private {destination.relative_to(ROOT)}; "
        "no secrets printed and no existing file overwritten."
    )


if __name__ == "__main__":
    main()
