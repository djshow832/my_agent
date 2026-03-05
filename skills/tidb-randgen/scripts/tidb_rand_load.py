#!/usr/bin/env python3

import argparse
import concurrent.futures
import json
import math
from typing import Any, Dict, List, Optional, Tuple

import os

from common import (
    connect_mysql,
    now_ms,
    qident,
    qname,
    read_json,
    rng_from_seed,
    write_json,
)
from envutil import getenv, load_dotenv


def gen_value(rng, col: Dict[str, Any], row_i: int, table_ctx: Dict[str, Any]):
    if col.get("auto_increment"):
        return None  # omitted
    if col.get("nullable") and rng.random() < 0.05:
        return None

    t = col["type"].upper()

    # special join key
    if col.get("join_key"):
        # ensure overlap across tables: use small keyspace
        return rng.randint(1, max(2, min(10000, table_ctx["row_count"] // 10)))

    if t.startswith("BIGINT") or t.startswith("INT"):
        # choose between uniform and hot distribution if indexed
        hot_pool = table_ctx.get("hot_int_pool")
        if hot_pool and rng.random() < 0.2:
            return rng.choice(hot_pool)
        return row_i + 1 if table_ctx.get("monotonic_int") else rng.randint(1, table_ctx["row_count"] * 2)

    if t.startswith("DECIMAL"):
        # stable decimal
        return float(rng.randint(0, 10_000_000)) / 100.0

    if t.startswith("VARCHAR"):
        n = int(t.split("(")[1].split(")")[0]) if "(" in t else 32
        base = f"s{row_i}_{col['name']}_{rng.randint(0, 1_000_000)}"
        return base[:n]

    if t.startswith("TEXT"):
        return f"txt_{row_i}_{rng.randint(0, 1_000_000)}"

    if t.startswith("DATETIME") or t.startswith("TIMESTAMP"):
        # 2000-01-01 + offset seconds
        sec = rng.randint(0, 3600 * 24 * 365 * 20)
        # return string; TiDB accepts
        return f"2000-01-01 00:00:00"  # keep simple for speed

    if t.startswith("DATE"):
        return "2000-01-01"

    # fallback
    return f"v{row_i}_{col['name']}"


def table_insert_sql(db: str, table: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    cols = [c for c in table["columns"] if not c.get("auto_increment")]
    col_names = ",".join(qident(c["name"]) for c in cols)
    placeholders = ",".join(["%s"] * len(cols))
    sql = f"INSERT INTO {qname(db, table['name'])} ({col_names}) VALUES ({placeholders})"
    return sql, cols


def load_one_table(
    *,
    dsn: Optional[str],
    host: Optional[str],
    port: int,
    user: Optional[str],
    password: str,
    tls_ca: Optional[str],
    tls_skip_verify: bool,
    seed: int,
    db: str,
    table: Dict[str, Any],
    batch: int,
) -> Dict[str, Any]:
    rng = rng_from_seed(seed ^ (hash(db + "." + table["name"]) & 0xFFFFFFFF))
    row_count = int(table["row_count"])

    # create a hot pool for int columns to shape selectivity
    hot_pool = [rng.randint(1, 1000) for _ in range(128)]

    # If PK is single int-ish column, generate monotonic for better clustering
    pk_cols = table["primary_key"]["columns"]
    monotonic_int = False
    if len(pk_cols) == 1:
        pk_name = pk_cols[0]
        pk_col = next((c for c in table["columns"] if c["name"] == pk_name), None)
        if pk_col and pk_col["type"] in ("INT", "BIGINT") and not pk_col.get("auto_increment"):
            monotonic_int = True

    table_ctx = {"row_count": row_count, "hot_int_pool": hot_pool, "monotonic_int": monotonic_int}

    conn = connect_mysql(
        dsn=dsn,
        host=host,
        port=port,
        user=user,
        password=password,
        db=db,
        tls_ca=tls_ca,
        tls_skip_verify=tls_skip_verify,
    )

    sql, cols = table_insert_sql(db, table)
    started = now_ms()
    inserted = 0
    errors = 0

    try:
        with conn.cursor() as cur:
            # speed knobs
            cur.execute("SET SESSION tidb_disable_txn_auto_retry = 1")

            buf = []
            for i in range(row_count):
                row = []
                for c in cols:
                    v = gen_value(rng, c, i, table_ctx)
                    row.append(v)
                buf.append(tuple(row))

                if len(buf) >= batch:
                    try:
                        cur.executemany(sql, buf)
                        inserted += len(buf)
                    except Exception:
                        errors += 1
                        # naive retry one by one
                        for r in buf:
                            try:
                                cur.execute(sql, r)
                                inserted += 1
                            except Exception:
                                errors += 1
                    buf = []

            if buf:
                try:
                    cur.executemany(sql, buf)
                    inserted += len(buf)
                except Exception:
                    errors += 1
                    for r in buf:
                        try:
                            cur.execute(sql, r)
                            inserted += 1
                        except Exception:
                            errors += 1
    finally:
        conn.close()

    ended = now_ms()
    return {
        "db": db,
        "table": table["name"],
        "target_rows": row_count,
        "inserted_rows": inserted,
        "errors": errors,
        "ms": ended - started,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=".env")
    ap.add_argument("--dsn", help="If omitted, read TIDB_DNS from .env")
    ap.add_argument("--host")
    ap.add_argument("--port", type=int, default=4000)
    ap.add_argument("--user")
    ap.add_argument("--password", default="")
    ap.add_argument("--seed", type=int, required=True)

    ap.add_argument("--schema", help="schema_spec.json; if omitted, read from TIDB_SCHEMA_PATH/schema_spec.json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--batch", type=int, default=500)
    ap.add_argument("--tls-ca")
    ap.add_argument("--tls-skip-verify", action="store_true")

    args = ap.parse_args()

    env = load_dotenv(args.env)
    if not args.dsn:
        args.dsn = getenv(env, "TIDB_DNS")

    if not args.schema:
        sp = getenv(env, "TIDB_SCHEMA_PATH")
        if not sp:
            raise SystemExit("missing --schema and TIDB_SCHEMA_PATH is not set")
        args.schema = os.path.join(sp, "schema_spec.json")

    schema = read_json(args.schema)

    jobs = []
    for db in schema["dbs"]:
        for t in db["tables"]:
            jobs.append((db["name"], t))

    started = now_ms()
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = []
        for db_name, t in jobs:
            futs.append(
                ex.submit(
                    load_one_table,
                    dsn=args.dsn,
                    host=args.host,
                    port=args.port,
                    user=args.user,
                    password=args.password,
                    tls_ca=args.tls_ca,
                    tls_skip_verify=args.tls_skip_verify,
                    seed=args.seed,
                    db=db_name,
                    table=t,
                    batch=args.batch,
                )
            )
        for f in concurrent.futures.as_completed(futs):
            results.append(f.result())

    ended = now_ms()

    report = {
        "version": 1,
        "seed": args.seed,
        "schema": args.schema,
        "started_ms": started,
        "ended_ms": ended,
        "total_ms": ended - started,
        "tables": sorted(results, key=lambda x: (x["db"], x["table"])),
        "summary": {
            "target_rows": sum(int(r["target_rows"]) for r in results),
            "inserted_rows": sum(int(r["inserted_rows"]) for r in results),
            "errors": sum(int(r["errors"]) for r in results),
        },
    }

    write_json(args.out, report)


if __name__ == "__main__":
    main()
