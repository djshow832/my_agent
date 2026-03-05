#!/usr/bin/env python3

import argparse
import json
from typing import Any, Dict, List, Optional, Tuple

import os

from common import clamp, piecewise_bucket_choice, qident, qname, read_json, rng_from_seed, write_json
from envutil import getenv, load_dotenv


def pick_table(rng, schema) -> Tuple[str, Dict[str, Any]]:
    db = rng.choice(schema["dbs"])
    t = rng.choice(db["tables"])
    return db["name"], t


def indexed_columns(table: Dict[str, Any]) -> List[str]:
    cols = set(table["primary_key"]["columns"])
    for uk in table.get("unique_keys", []):
        cols.update(uk["columns"])
    for idx in table.get("secondary_indexes", []):
        cols.update(idx["columns"])
    return [c for c in cols]


def non_text_columns(table: Dict[str, Any]) -> List[str]:
    out = []
    for c in table["columns"]:
        if not c["type"].upper().startswith("TEXT"):
            out.append(c["name"])
    return out


def gen_templates(schema: Dict[str, Any], rng) -> List[Dict[str, Any]]:
    templates: List[Dict[str, Any]] = []

    # Basic template families derived from schema.
    for db in schema["dbs"]:
        for t in db["tables"]:
            dbn = db["name"]
            tn = t["name"]
            fq = qname(dbn, tn)

            pk_cols = t["primary_key"]["columns"]
            # point select/update/delete using PK if single-column
            if len(pk_cols) == 1:
                pk = pk_cols[0]
                templates.append(
                    {
                        "name": f"point_select_pk::{dbn}.{tn}",
                        "weight": 0.18,
                        "kind": "DQL",
                        "sql": f"SELECT * FROM {fq} WHERE {qident(pk)}=%s",
                        "params": {"p": {"source": "pk", "db": dbn, "table": tn, "column": pk}},
                        "expected_rows": 1,
                        "complexity": "point",
                        "operators": ["index_lookup"],
                    }
                )
                templates.append(
                    {
                        "name": f"point_update_pk::{dbn}.{tn}",
                        "weight": 0.06,
                        "kind": "DML",
                        "sql": f"UPDATE {fq} SET {qident(pk)}={qident(pk)} WHERE {qident(pk)}=%s",
                        "params": {"p": {"source": "pk", "db": dbn, "table": tn, "column": pk}},
                        "expected_rows": 1,
                        "complexity": "point",
                        "operators": ["index_lookup"],
                    }
                )

            # range select using an indexed non-text column if exists
            idx_cols = indexed_columns(t)
            cand = [c for c in idx_cols if c in non_text_columns(t)]
            if cand:
                col = rng.choice(cand)
                templates.append(
                    {
                        "name": f"range_select_idx_small::{dbn}.{tn}.{col}",
                        "weight": 0.10,
                        "kind": "DQL",
                        "sql": f"SELECT * FROM {fq} WHERE {qident(col)} BETWEEN %s AND %s LIMIT 1000",
                        "params": {
                            "lo": {"source": "range", "db": dbn, "table": tn, "column": col, "target": "small"},
                            "hi": {"source": "range", "db": dbn, "table": tn, "column": col, "target": "small"},
                        },
                        "expected_rows": 1000,
                        "complexity": "k1",
                        "operators": ["index_range"],
                    }
                )
                templates.append(
                    {
                        "name": f"range_select_idx_large::{dbn}.{tn}.{col}",
                        "weight": 0.02,
                        "kind": "DQL",
                        "sql": f"SELECT COUNT(*) AS c FROM {fq} WHERE {qident(col)} BETWEEN %s AND %s",
                        "params": {
                            "lo": {"source": "range", "db": dbn, "table": tn, "column": col, "target": "large"},
                            "hi": {"source": "range", "db": dbn, "table": tn, "column": col, "target": "large"},
                        },
                        "expected_rows": min(1_000_000, int(t["row_count"])),
                        "complexity": "m1",
                        "operators": ["index_range", "agg"],
                    }
                )

            # insert template (avoid specifying auto_increment cols)
            ins_cols = [c for c in t["columns"] if not c.get("auto_increment")]
            if ins_cols:
                cols_sql = ",".join(qident(c["name"]) for c in ins_cols)
                vals_sql = ",".join(["%s"] * len(ins_cols))
                templates.append(
                    {
                        "name": f"insert_row::{dbn}.{tn}",
                        "weight": 0.06,
                        "kind": "DML",
                        "sql": f"INSERT INTO {fq} ({cols_sql}) VALUES ({vals_sql})",
                        "params": {c["name"]: {"source": "gen", "db": dbn, "table": tn, "column": c["name"]} for c in ins_cols},
                        "expected_rows": 1,
                        "complexity": "point",
                        "operators": ["insert"],
                    }
                )

            # DDL templates (safe only, no DROP)
            # Add an index on a random non-text column not already indexed.
            indexed = set(indexed_columns(t))
            candidates = [c for c in non_text_columns(t) if c not in indexed]
            if candidates:
                c = rng.choice(candidates)
                templates.append(
                    {
                        "name": f"ddl_add_index::{dbn}.{tn}.{c}",
                        "weight": 0.002,
                        "kind": "DDL",
                        "sql": f"ALTER TABLE {fq} ADD INDEX {qident('ddl_idx_' + c)} ({qident(c)})",
                        "params": {},
                        "expected_rows": 0,
                        "complexity": "ddl",
                        "operators": ["ddl"],
                    }
                )

            templates.append(
                {
                    "name": f"analyze_table::{dbn}.{tn}",
                    "weight": 0.001,
                    "kind": "DDL",
                    "sql": f"ANALYZE TABLE {fq}",
                    "params": {},
                    "expected_rows": 0,
                    "complexity": "ddl",
                    "operators": ["ddl"],
                }
            )

    # Join templates derived from join_edges
    for e in schema.get("join_edges", []):
        dbn = e["db"]
        left = e["left"]
        right = e["right"]
        col = e["col"]
        templates.append(
            {
                "name": f"join_select::{dbn}.{left}_x_{right}",
                "weight": 0.02,
                "kind": "DQL",
                "sql": f"SELECT COUNT(*) AS c FROM {qname(dbn,left)} a JOIN {qname(dbn,right)} b ON a.{qident(col)}=b.{qident(col)} WHERE a.{qident(col)} BETWEEN %s AND %s",
                "params": {
                    "lo": {"source": "range", "db": dbn, "table": left, "column": col, "target": "small"},
                    "hi": {"source": "range", "db": dbn, "table": left, "column": col, "target": "small"},
                },
                "expected_rows": 1000,
                "complexity": "k1",
                "operators": ["join", "agg"],
            }
        )

    # Normalize weights to be non-zero overall
    s = sum(max(0.0, float(t["weight"])) for t in templates)
    if s <= 0:
        for t in templates:
            t["weight"] = 1.0
    return templates


def gen_workload_spec(schema: Dict[str, Any], rng) -> Dict[str, Any]:
    # Defaults based on your requested ranges, but runner can override.
    concurrency_min = 1000
    concurrency_max = 10000
    if rng.random() < 0.5:
        concurrency_min = 200
        concurrency_max = 3000

    spec = {
        "version": 1,
        "seed": None,
        "connections": {
            "lifetime": {
                "long": 0.90,
                "short": 0.10,
                "long_seconds": {"dist": "uniform", "min": 600, "max": 3600},
                "short_seconds": {"dist": "uniform", "min": 5, "max": 60},
            },
            "concurrency": {
                "min": concurrency_min,
                "max": concurrency_max,
                "waveform": "random_walk",
                "step": {"dist": "uniform", "min": 50, "max": 500},
                "interval_seconds": 5,
            },
        },
        "transactions": {
            "explicit_time_ratio": 0.10,
            "txn_len": {"dist": "piecewise", "buckets": [["1", 0.70], ["2-5", 0.25], ["6-20", 0.05]]},
            "idle_ms": {"busy": {"dist": "uniform", "min": 0, "max": 20}, "idle": {"dist": "uniform", "min": 50, "max": 500}},
            "busy_conn_ratio": 0.30,
        },
        "mix": {
            "DDL": 0.01,
            "DQL": 0.90,
            "DML": 0.09,
            "no_drop": True,
        },
        "complexity": {
            "buckets": {
                "point": 0.90,
                "k1": 0.09,
                "m1": 0.01,
            }
        },
        "operators": {
            "join": 0.05,
            "agg": 0.08,
            "index_lookup": 0.60,
            "index_range": 0.20,
            "table_scan": 0.02,
        },
    }
    return spec


def write_templates_jsonl(path: str, templates: List[Dict[str, Any]]):
    with open(path, "w", encoding="utf-8") as f:
        for t in templates:
            f.write(json.dumps(t, sort_keys=True))
            f.write("\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=".env")
    ap.add_argument("--schema", help="schema_spec.json; if omitted, read from TIDB_SCHEMA_PATH/schema_spec.json")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--templates", required=True)
    args = ap.parse_args()

    env = load_dotenv(args.env)
    if not args.schema:
        sp = getenv(env, "TIDB_SCHEMA_PATH")
        if not sp:
            raise SystemExit("missing --schema and TIDB_SCHEMA_PATH is not set")
        args.schema = os.path.join(sp, "schema_spec.json")

    schema = read_json(args.schema)
    rng = rng_from_seed(args.seed)

    wl = gen_workload_spec(schema, rng)
    wl["seed"] = args.seed

    templates = gen_templates(schema, rng)

    # Lightweight post-pass: set complexity buckets on templates based on expected_rows.
    for t in templates:
        if t.get("complexity") not in ("ddl", "point", "k1", "m1"):
            er = int(t.get("expected_rows") or 0)
            if er <= 2:
                t["complexity"] = "point"
            elif er <= 2000:
                t["complexity"] = "k1"
            else:
                t["complexity"] = "m1"

    write_json(args.out, {**wl, "templates_summary": {"count": len(templates)}})
    write_templates_jsonl(args.templates, templates)


if __name__ == "__main__":
    main()
