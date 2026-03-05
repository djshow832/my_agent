import json
import math
import os
import random
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


def rng_from_seed(seed: int) -> random.Random:
    return random.Random(int(seed))


def qident(name: str) -> str:
    # MySQL identifier quoting with backticks.
    return "`" + name.replace("`", "``") + "`"


def qname(db: str, table: str) -> str:
    return f"{qident(db)}.{qident(table)}"


def clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def weighted_choice(rng: random.Random, items: Sequence[Tuple[Any, float]]):
    total = sum(w for _, w in items)
    if total <= 0:
        raise ValueError("total weight must be > 0")
    x = rng.random() * total
    s = 0.0
    for item, w in items:
        s += w
        if x <= s:
            return item
    return items[-1][0]


def piecewise_bucket_choice(rng: random.Random, buckets: Sequence[Tuple[str, float]]):
    return weighted_choice(rng, list(buckets))


def approx_bytes_for_row(col_types: List[Dict[str, Any]]) -> int:
    # Very rough row size estimation for planning row counts.
    # Keep it simple; correctness is not required, only scale.
    size = 0
    for c in col_types:
        t = c["type"].upper()
        if t.startswith("BIGINT"):
            size += 8
        elif t.startswith("INT"):
            size += 4
        elif t.startswith("DECIMAL"):
            size += 8
        elif t.startswith("DATETIME") or t.startswith("TIMESTAMP"):
            size += 8
        elif t.startswith("DATE"):
            size += 4
        elif t.startswith("VARCHAR"):
            m = re.search(r"VARCHAR\((\d+)\)", t)
            n = int(m.group(1)) if m else 32
            size += min(n, 64)  # average
        elif t.startswith("TEXT"):
            size += 64
        elif t.startswith("JSON"):
            size += 64
        elif t.startswith("BLOB"):
            size += 64
        else:
            size += 16
    return max(size, 16)


def ensure_dir(path: str):
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)


def write_json(path: str, obj: Any):
    ensure_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")


def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# --- MySQL/TiDB connection helpers (pymysql) ---

def _require_pymysql():
    try:
        import pymysql  # noqa: F401
    except Exception as e:
        raise RuntimeError(
            "Missing dependency: pymysql. Install with: python3 -m pip install --user pymysql"
        ) from e


def parse_mysql_dsn(dsn: str) -> Dict[str, Any]:
    # mysql://user:pass@host:port/db
    # Note: password may contain special chars; keep this basic for now.
    m = re.match(r"^mysql://(?P<user>[^:@/]+)(:(?P<pw>[^@/]*))?@(?P<host>[^:/]+)(:(?P<port>\d+))?(/(?P<db>[^?]+))?", dsn)
    if not m:
        raise ValueError(f"invalid DSN: {dsn}")
    d = m.groupdict()
    return {
        "user": d["user"],
        "password": d.get("pw") or "",
        "host": d["host"],
        "port": int(d.get("port") or 4000),
        "db": d.get("db") or None,
    }


def connect_mysql(
    *,
    dsn: Optional[str] = None,
    host: Optional[str] = None,
    port: int = 4000,
    user: Optional[str] = None,
    password: str = "",
    db: Optional[str] = None,
    tls_ca: Optional[str] = None,
    tls_skip_verify: bool = False,
):
    _require_pymysql()
    import ssl
    import pymysql

    if dsn:
        parts = parse_mysql_dsn(dsn)
        host = parts["host"]
        port = parts["port"]
        user = parts["user"]
        password = parts["password"]
        db = db or parts.get("db")

    if not host or not user:
        raise ValueError("host and user are required (or pass --dsn)")

    ssl_params = None
    if tls_ca or tls_skip_verify:
        ctx = ssl.create_default_context(cafile=tls_ca) if tls_ca else ssl.create_default_context()
        if tls_skip_verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        ssl_params = {"ssl": ctx}

    conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db,
        autocommit=True,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        **(ssl_params or {}),
    )
    return conn


def exec_many(conn, sql: str, params_iter: Iterable[Tuple[Any, ...]]):
    with conn.cursor() as cur:
        cur.executemany(sql, list(params_iter))


def exec_one(conn, sql: str, params: Optional[Tuple[Any, ...]] = None):
    with conn.cursor() as cur:
        cur.execute(sql, params)


def fetch_all(conn, sql: str, params: Optional[Tuple[Any, ...]] = None) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def now_ms() -> int:
    return int(time.time() * 1000)
