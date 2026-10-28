"""Private stdin protocol keeping the exported PostgreSQL snapshot alive."""

import argparse
import json
import os
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-database", required=True)
    options = parser.parse_args()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    import django

    django.setup()
    from django.db import connection

    from scripts.recovery_state import capture_state, read_snapshot

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT current_database(),current_user,"
                "current_setting('server_version_num')::int,current_setting('server_encoding')"
            )
            name, role, version, encoding = cursor.fetchone()
            cursor.execute(
                "SELECT datcollate,datctype,datlocprovider FROM pg_database "
                "WHERE datname=current_database()"
            )
            collation, ctype, provider = cursor.fetchone()
        if (
            name != options.expected_database
            or role != "olist_owner"
            or version // 10000 != 17
            or encoding != "UTF8"
            or provider != "c"
        ):
            raise RuntimeError("Wrong recovery snapshot identity.")
        with read_snapshot(connection) as token:
            print(
                json.dumps(
                    {
                        "snapshot": token,
                        "database": name,
                        "postgresql_version_num": version,
                        "collation": collation,
                        "ctype": ctype,
                    }
                ),
                flush=True,
            )
            for line in sys.stdin:
                request = json.loads(line)
                if request == {"action": "capture"}:
                    print(json.dumps(capture_state(connection), sort_keys=True), flush=True)
                elif request == {"action": "finish"}:
                    break
                else:
                    raise RuntimeError("Unsupported recovery protocol request.")
    except Exception:
        print(json.dumps({"error": "Read-only recovery capture failed."}), flush=True)
        raise SystemExit(1) from None
    finally:
        connection.close()


if __name__ == "__main__":
    main()
