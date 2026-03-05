#!/usr/bin/env python3

import argparse
from typing import Any, Dict, List, Optional, Tuple

from common import (
    approx_bytes_for_row,
    clamp,
    connect_mysql,
    qident,
    qname,
    rng_from_seed,
    write_json,
)


def gen_column(rng, col_id: int, allow_auto_inc: bool) -> Dict[str, Any]:
    # Keep types TiDB-friendly.
    type_pool: List[Tuple[str, float]] = [
        ("BIGINT", 0.30),
        ("INT", 0.20),
        ("DECIMAL(20,6)", 0.05),
        ("VARCHAR(32)", 0.20),
        ("VARCHAR(128)", 0.10),
        ("TEXT", 0.05),
        ("DATETIME", 0.05),
        ("DATE", 0.05),
    ]

    # weighted choice
    total = sum(w for _, w in type_pool)
    x = rng.random() * total
    s = 0.0
    col_type = type_pool[-1][0]
    for t, w in type_pool:
        s += w
        if x <= s:
            col_type = t
            break

    nullable = rng.random() < 0.1
    has_default = rng.random() < 0.2

    is_auto_inc = False
    if allow_auto_inc and (col_type in ("BIGINT", "INT")) and rng.random() < 0.20:
        is_auto_inc = True
        nullable = False
        has_default = False

    return {
        "name": f"c{col_id}",
        "type": col_type,
        "nullable": nullable,
        "has_default": has_default,
        "auto_increment": is_auto_inc,
    }


def choose_index_cols(rng, columns: List[Dict[str, Any]], max_len: int) -> List[str]:
    # avoid TEXT for indexes by default
    candidates = [c["name"] for c in columns if not c["type"].upper().startswith("TEXT")]
    if not candidates:
        candidates = [c["name"] for c in columns]
    k = clamp(int(rng.randint(1, max_len)), 1, min(max_len, len(candidates)))
    rng.shuffle(candidates)
    return candidates[:k]


def create_table_ddl(db: str, t: Dict[str, Any]) -> str:
    col_ddls = []
    pk_cols = t["primary_key"]["columns"]

    for c in t["columns"]:
        parts = [qident(c["name"]), c["type"]]
        if not c["nullable"]:
            parts.append("NOT NULL")
        if c.get("auto_increment"):
            parts.append("AUTO_INCREMENT")
        if c.get("has_default"):
            # Use simple defaults only.
            t_upper = c["type"].upper()
            if t_upper.startswith("VARCHAR") or t_upper.startswith("TEXT"):
                parts.append("DEFAULT ''")
            elif t_upper.startswith("DATE"):
                parts.append("DEFAULT '2000-01-01'")
            elif t_upper.startswith("DATETIME") or t_upper.startswith("TIMESTAMP"):
                parts.append("DEFAULT '2000-01-01 00:00:00'")
            else:
                parts.append("DEFAULT 0")
        col_ddls.append(" ".join(parts))

    # keys
    pk_clause = f"PRIMARY KEY ({', '.join(qident(c) for c in pk_cols)})"
    idx_clauses = [pk_clause]

    for uk in t.get("unique_keys", []):
        cols = ", ".join(qident(c) for c in uk["columns"])
        idx_clauses.append(f"UNIQUE KEY {qident(uk['name'])} ({cols})")

    for idx in t.get("secondary_indexes", []):
        cols = ", ".join(qident(c) for c in idx["columns"])
        idx_clauses.append(f"KEY {qident(idx['name'])} ({cols})")

    partition_clause = ""
    if t.get("partition"):
        p = t["partition"]
        if p["type"] == "RANGE":
            # RANGE partition; boundaries stored in spec.
            expr = qident(p["column"])
            parts = []
            for i, bound in enumerate(p["bounds"]):
                parts.append(f"PARTITION p{i} VALUES LESS THAN ({bound})")
            partition_clause = f"PARTITION BY RANGE ({expr}) (" + ", ".join(parts) + ")"

    ddl = (
        f"CREATE TABLE {qname(db, t['name'])} (\n  "
        + ",\n  ".join(col_ddls + idx_clauses)
        + "\n)"
    )

    if partition_clause:
        ddl += " " + partition_clause

    ddl += " DEFAULT CHARSET=utf8mb4"
    return ddl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", help="mysql://user:pass@host:port[/db]")
    ap.add_argument("--host")
    ap.add_argument("--port", type=int, default=4000)
    ap.add_argument("--user")
    ap.add_argument("--password", default="")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--target-bytes", type=int, default=50_000_000, help="approx total data bytes target")
    ap.add_argument("--apply", action="store_true", help="execute DDL on target")
    ap.add_argument("--tls-ca")
    ap.add_argument("--tls-skip-verify", action="store_true")

    ap.add_argument("--db-min", type=int, default=1)
    ap.add_argument("--db-max", type=int, default=4)
    ap.add_argument("--tables-min", type=int, default=2)
    ap.add_argument("--tables-max", type=int, default=12)
    ap.add_argument("--cols-min", type=int, default=6)
    ap.add_argument("--cols-max", type=int, default=24)

    args = ap.parse_args()

    rng = rng_from_seed(args.seed)

    db_count = rng.randint(args.db_min, args.db_max)

    spec: Dict[str, Any] = {
        "version": 1,
        "seed": args.seed,
        "target_bytes": args.target_bytes,
        "dbs": [],
        "ddl": [],
    }

    # Build schema
    all_tables: List[Dict[str, Any]] = []
    for db_i in range(db_count):
        db_name = f"db_{db_i}"
        t_count = rng.randint(args.tables_min, args.tables_max)
        db_obj = {"name": db_name, "tables": []}

        for t_i in range(t_count):
            t_name = f"t_{t_i}"
            col_count = rng.randint(args.cols_min, args.cols_max)

            # auto-inc allowed only once per table
            allow_ai = True
            cols = []
            for c_i in range(col_count):
                c = gen_column(rng, c_i, allow_ai)
                if c.get("auto_increment"):
                    allow_ai = False
                cols.append(c)

            # primary key
            pk_cols = choose_index_cols(rng, cols, max_len=2 if rng.random() < 0.7 else 3)
            pk = {
                "name": "PRIMARY",
                "columns": pk_cols,
                "clustered": True if rng.random() < 0.7 else False,
            }

            # unique keys
            unique_keys = []
            for u_i in range(rng.randint(0, 2)):
                uk_cols = choose_index_cols(rng, cols, max_len=2)
                unique_keys.append({"name": f"uk_{u_i}", "columns": uk_cols})

            # secondary indexes
            secondary_indexes = []
            for s_i in range(rng.randint(0, 4)):
                idx_cols = choose_index_cols(rng, cols, max_len=3)
                secondary_indexes.append({"name": f"idx_{s_i}", "columns": idx_cols})

            # partition (optional)
            partition = None
            if rng.random() < 0.15:
                # choose an INT/BIGINT/DATE column
                cand = [c for c in cols if c["type"] in ("INT", "BIGINT", "DATE")]
                if cand:
                    pc = rng.choice(cand)
                    if pc["type"] == "DATE":
                        bounds = ["'2005-01-01'", "'2010-01-01'", "'2015-01-01'", "'2020-01-01'", "'2025-01-01'"]
                    else:
                        bounds = ["1000", "10000", "100000", "1000000"]
                    partition = {"type": "RANGE", "column": pc["name"], "bounds": bounds}

            # row count target derived later
            table = {
                "name": t_name,
                "columns": cols,
                "primary_key": pk,
                "unique_keys": unique_keys,
                "secondary_indexes": secondary_indexes,
                "partition": partition,
                "row_count": None,
                "selectivity": {},
            }

            db_obj["tables"].append(table)
            all_tables.append({"db": db_name, **table})

        spec["dbs"].append(db_obj)

    # Plan row counts to hit target bytes (rough)
    per_table_sizes = []
    for t in all_tables:
        est = approx_bytes_for_row(t["columns"])
        per_table_sizes.append(est)

    total_est = sum(per_table_sizes)
    if total_est <= 0:
        total_est = 1

    # allocate bytes proportionally but with randomness
    target = args.target_bytes
    for i, t in enumerate(all_tables):
        base_share = per_table_sizes[i] / total_est
        # randomize table size a bit
        mult = 0.3 + rng.random() * 2.5
        bytes_for_table = max(int(target * base_share * mult / len(all_tables) * len(all_tables)), 1024)
        row_size = per_table_sizes[i]
        rows = clamp(int(bytes_for_table / max(row_size, 1)), 100, 2_000_000)
        t["row_count"] = rows

        # selectivity profiles for indexed columns
        sel = {
            "point": 1,
            "small": min(1000, rows),
            "large": min(1_000_000, rows),
        }
        t["selectivity"] = {
            "primary_key": sel,
            "unique_keys": sel,
            "secondary_indexes": sel,
        }

    # Write back row_count into nested spec
    for db in spec["dbs"]:
        for table in db["tables"]:
            match = next(
                (t for t in all_tables if t["db"] == db["name"] and t["name"] == table["name"]),
                None,
            )
            if match:
                table["row_count"] = match["row_count"]
                table["selectivity"] = match["selectivity"]

    # Join relationships (optional): add a shared join key col in some tables
    # Note: we only record join graph here; actual column injection is done by load script if present.
    join_edges = []
    for db in spec["dbs"]:
        tables = db["tables"]
        if len(tables) >= 2 and rng.random() < 0.5:
            a = rng.choice(tables)
            b = rng.choice([t for t in tables if t is not a])
            join_col = "k_join"
            # ensure both tables have k_join BIGINT
            for t in (a, b):
                if not any(c["name"] == join_col for c in t["columns"]):
                    t["columns"].append(
                        {
                            "name": join_col,
                            "type": "BIGINT",
                            "nullable": False,
                            "has_default": False,
                            "auto_increment": False,
                            "join_key": True,
                        }
                    )
            join_edges.append({"db": db["name"], "left": a["name"], "right": b["name"], "col": join_col})

    spec["join_edges"] = join_edges

    # DDL statements
    ddls: List[str] = []
    for db in spec["dbs"]:
        ddls.append(f"CREATE DATABASE IF NOT EXISTS {qident(db['name'])}")
        for t in db["tables"]:
            ddls.append(create_table_ddl(db["name"], t))

    spec["ddl"] = ddls

    write_json(args.out, spec)

    if args.apply:
        conn = connect_mysql(
            dsn=args.dsn,
            host=args.host,
            port=args.port,
            user=args.user,
            password=args.password,
            tls_ca=args.tls_ca,
            tls_skip_verify=args.tls_skip_verify,
        )
        try:
            with conn.cursor() as cur:
                for s in ddls:
                    cur.execute(s)
        finally:
            conn.close()


if __name__ == "__main__":
    main()
