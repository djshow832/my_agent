#!/usr/bin/env python3

"""tidb_rand_run.py

Minimal executable workload runner for tidb-randgen templates.

Goals:
- Execute generated sql_templates.jsonl against TiDB/MySQL.
- Generate params for template param sources:
  - pk/col/range: sample from existing rows (cached per table)
  - gen: generate type-aware values for INSERT templates

This is intentionally simple (single-thread loop). You can wrap it with your
own concurrency harness if needed.
"""

import argparse
import datetime as dt
import json
import os
import random
import time
from typing import Any, Dict, List, Optional, Tuple

from common import connect_mysql, read_json
from envutil import getenv, load_dotenv


def _load_templates(path: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def _index_schema(schema: Dict[str, Any]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    idx: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for db in schema.get("dbs", []):
        for t in db.get("tables", []):
            idx[(db["name"], t["name"])] = t
    return idx


def _gen_value(rng: random.Random, col_type: str) -> Any:
    t = col_type.upper()
    # numeric
    if t.startswith("BIGINT"):
        return rng.randint(1, 2**63 - 1)
    if t.startswith("INT"):
        return rng.randint(1, 2**31 - 1)
    if t.startswith("TINYINT"):
        return rng.randint(0, 127)
    if t.startswith("SMALLINT"):
        return rng.randint(0, 32767)
    if t.startswith("MEDIUMINT"):
        return rng.randint(0, 8388607)
    if t.startswith("DECIMAL"):
        # return as string to avoid float formatting issues
        return f"{rng.random()*1e6:.6f}"

    # text
    if t.startswith("VARCHAR"):
        # keep it short
        return f"v{rng.randint(1, 10_000_000)}"
    if t.startswith("TEXT"):
        return f"t{rng.randint(1, 10_000_000)}"

    # datetime/date
    if t.startswith("DATETIME") or t.startswith("TIMESTAMP"):
        base = dt.datetime(2000, 1, 1)
        return base + dt.timedelta(seconds=rng.randint(0, 3600 * 24 * 365 * 10))
    if t.startswith("DATE"):
        base = dt.date(2000, 1, 1)
        return base + dt.timedelta(days=rng.randint(0, 365 * 10))

    # fallback
    return rng.randint(1, 1_000_000)


def _pick_table_from_params(params: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    for p in params.values():
        if isinstance(p, dict) and p.get("db") and p.get("table"):
            return p.get("db"), p.get("table")
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=".env")
    ap.add_argument("--dsn", help="If omitted, read TIDB_DNS from .env")
    ap.add_argument("--schema", help="schema_spec.json; if omitted, read from TIDB_SCHEMA_PATH/schema_spec.json")
    ap.add_argument("--templates", required=True, help="sql_templates.jsonl")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--ops", type=int, default=1000, help="number of statements to execute")
    ap.add_argument(
        "--duration-seconds",
        type=int,
        default=0,
        help="run for N seconds (0 = disabled); stops when duration or --ops limit reached",
    )
    ap.add_argument("--include-ddl", action="store_true", help="include DDL templates (default: off)")
    ap.add_argument("--tls-ca")
    ap.add_argument("--tls-skip-verify", action="store_true")
    ap.add_argument("--max-errors", type=int, default=10)

    args = ap.parse_args()

    env = load_dotenv(args.env)
    dsn = args.dsn or getenv(env, "TIDB_DNS")
    if not dsn:
        raise SystemExit("missing --dsn (or set TIDB_DNS in .env)")

    schema_path = getenv(env, "TIDB_SCHEMA_PATH")
    schema_file = args.schema
    if not schema_file:
        if not schema_path:
            raise SystemExit("missing --schema (or set TIDB_SCHEMA_PATH in .env)")
        schema_file = os.path.join(schema_path, "schema_spec.json")

    schema = read_json(schema_file)
    # Schema spec is useful, but the authoritative types are whatever is actually
    # in the cluster (in case you re-used DB names across runs). We'll still keep
    # the spec index as a fallback.
    table_idx = _index_schema(schema)

    templates = _load_templates(args.templates)
    if not args.include_ddl:
        templates = [t for t in templates if t.get("kind") != "DDL"]

    if not templates:
        raise SystemExit("no templates to run")

    weights = [max(0.0, float(t.get("weight", 1.0))) for t in templates]
    if sum(weights) <= 0:
        weights = [1.0] * len(templates)

    rng = random.Random(args.seed)

    conn = connect_mysql(dsn=dsn, tls_ca=args.tls_ca, tls_skip_verify=args.tls_skip_verify)

    # Cache one sample row per table for pk/col/range value sources.
    sample_cache: Dict[Tuple[str, str], Optional[Dict[str, Any]]] = {}

    # Cache actual column types from the cluster (SHOW COLUMNS).
    coltype_cache: Dict[Tuple[str, str], Dict[str, str]] = {}

    def sample_row(db: str, table: str) -> Optional[Dict[str, Any]]:
        key = (db, table)
        if key in sample_cache:
            return sample_cache[key]
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM `{db}`.`{table}` LIMIT 1")
            row = cur.fetchone()
        sample_cache[key] = row
        return row

    def get_coltypes(db: str, table: str) -> Dict[str, str]:
        key = (db, table)
        if key in coltype_cache:
            return coltype_cache[key]
        with conn.cursor() as cur:
            cur.execute(f"SHOW COLUMNS FROM `{db}`.`{table}`")
            rows = cur.fetchall() or []
        # DictCursor: Field, Type, Null, Key, Default, Extra
        m = {r["Field"]: r["Type"] for r in rows}
        coltype_cache[key] = m
        return m

    ok = 0
    errs = 0

    start = time.time()
    next_report = start + 5.0
    executed = 0

    try:
        while True:
            if executed >= args.ops:
                break
            if args.duration_seconds and (time.time() - start) >= float(args.duration_seconds):
                break

            tpl = rng.choices(templates, weights=weights, k=1)[0]
            sql = tpl["sql"]
            params_spec = tpl.get("params") or {}
            db, table = _pick_table_from_params(params_spec)

            row = None
            if db and table:
                row = sample_row(db, table)

            bound: List[Any] = []
            for _name, ps in params_spec.items():
                src = ps.get("source")
                if src in ("pk", "col", "range") and row is not None:
                    bound.append(row[ps["column"]])
                elif src == "gen":
                    # Prefer live column types from the cluster.
                    col_type = None
                    if ps.get("db") and ps.get("table"):
                        col_type = get_coltypes(ps["db"], ps["table"]).get(ps.get("column"))

                    # Fallback to schema spec.
                    if not col_type:
                        t_spec = table_idx.get((ps.get("db"), ps.get("table")))
                        if t_spec:
                            for c in t_spec.get("columns", []):
                                if c.get("name") == ps.get("column"):
                                    col_type = c.get("type")
                                    break

                    bound.append(_gen_value(rng, col_type or "INT"))
                else:
                    bound.append(1)

            try:
                with conn.cursor() as cur:
                    cur.execute(sql, tuple(bound))
                    if tpl.get("kind") == "DQL":
                        cur.fetchall()
                ok += 1
            except Exception as e:
                errs += 1
                if errs <= args.max_errors:
                    print("ERROR", tpl.get("name"), e, flush=True)
                    print("SQL", sql, flush=True)
                    print("PARAMS", tuple(bound), flush=True)
                if errs >= args.max_errors:
                    raise

            executed += 1

            now = time.time()
            if now >= next_report:
                elapsed = max(0.001, now - start)
                print(
                    json.dumps(
                        {
                            "elapsed_s": round(elapsed, 3),
                            "executed": executed,
                            "ok": ok,
                            "errors": errs,
                            "qps": round(executed / elapsed, 3),
                        }
                    ),
                    flush=True,
                )
                next_report = now + 5.0

        elapsed = max(0.001, time.time() - start)
        print(
            json.dumps(
                {
                    "elapsed_s": round(elapsed, 3),
                    "executed": executed,
                    "ok": ok,
                    "errors": errs,
                    "qps": round(executed / elapsed, 3),
                },
                indent=2,
            ),
            flush=True,
        )

    finally:
        conn.close()


if __name__ == "__main__":
    main()
