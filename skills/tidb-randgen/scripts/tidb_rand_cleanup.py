#!/usr/bin/env python3

import argparse
import os
import shutil
from typing import List, Optional

from common import connect_mysql, qident, read_json
from envutil import getenv, load_dotenv


def drop_databases(conn, db_names: List[str]):
    with conn.cursor() as cur:
        for db in db_names:
            cur.execute(f"DROP DATABASE IF EXISTS {qident(db)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=".env")
    ap.add_argument("--dsn", help="If omitted, read TIDB_DNS from .env")
    ap.add_argument("--schema", help="schema_spec.json; if omitted, read from TIDB_SCHEMA_PATH/schema_spec.json")
    ap.add_argument("--schema-path", help="directory to delete; if omitted read TIDB_SCHEMA_PATH")
    ap.add_argument("--tls-ca")
    ap.add_argument("--tls-skip-verify", action="store_true")

    ap.add_argument("--drop-dbs", action="store_true", help="drop databases recorded in schema_spec")
    ap.add_argument("--delete-schema-dir", action="store_true", help="delete TIDB_SCHEMA_PATH directory")
    ap.add_argument("--yes", action="store_true", help="required to perform destructive actions")

    args = ap.parse_args()

    env = load_dotenv(args.env)

    if not args.dsn:
        args.dsn = getenv(env, "TIDB_DNS")

    schema_path = args.schema_path or getenv(env, "TIDB_SCHEMA_PATH")

    if not args.schema:
        if not schema_path:
            raise SystemExit("missing --schema and TIDB_SCHEMA_PATH is not set")
        args.schema = os.path.join(schema_path, "schema_spec.json")

    if not (args.drop_dbs or args.delete_schema_dir):
        raise SystemExit("nothing to do: pass --drop-dbs and/or --delete-schema-dir")

    if not args.yes:
        raise SystemExit(
            "refusing to run without --yes (destructive). Example: "
            "python3 skills/tidb-randgen/scripts/tidb_rand_cleanup.py --drop-dbs --delete-schema-dir --yes"
        )

    schema = read_json(args.schema)
    db_names = [db["name"] for db in schema.get("dbs", [])]

    if args.drop_dbs:
        if not args.dsn:
            raise SystemExit("missing DSN (set TIDB_DNS or pass --dsn)")
        conn = connect_mysql(dsn=args.dsn, tls_ca=args.tls_ca, tls_skip_verify=args.tls_skip_verify)
        try:
            drop_databases(conn, db_names)
        finally:
            conn.close()

    if args.delete_schema_dir:
        if not schema_path:
            raise SystemExit("missing schema directory (set TIDB_SCHEMA_PATH or pass --schema-path)")
        sp = os.path.abspath(schema_path)
        # Safety guards
        if sp in ("/", "/root", os.path.abspath(os.path.expanduser("~"))):
            raise SystemExit(f"refusing to delete unsafe path: {sp}")
        if os.path.exists(sp):
            shutil.rmtree(sp)


if __name__ == "__main__":
    main()
