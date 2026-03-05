#!/usr/bin/env python3

import json
import urllib.request
from typing import Any, Dict, Optional


ZERO_API = "https://zero.tidbapi.com/v1alpha1/instances"


def provision(tag: Optional[str] = None) -> Dict[str, Any]:
    payload = {} if not tag else {"tag": tag}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(ZERO_API, method="POST", data=data)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


def to_mysql_dsn(instance_resp: Dict[str, Any]) -> str:
    inst = instance_resp.get("instance") or {}
    conn = inst.get("connection") or {}
    host = conn.get("host")
    port = conn.get("port", 4000)
    user = conn.get("username")
    pw = conn.get("password")
    # TiDB Cloud Zero typically requires TLS; we keep DSN generic and let client enable TLS via flags.
    return f"mysql://{user}:{pw}@{host}:{port}"
