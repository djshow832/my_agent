import os
import re
from typing import Dict, Optional


ENV_LINE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$")


def load_dotenv(path: str) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not os.path.exists(path):
        return env
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = ENV_LINE.match(line)
            if not m:
                continue
            k, v = m.group(1), m.group(2)
            # strip surrounding quotes if present
            if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
                v = v[1:-1]
            env[k] = v
    return env


def upsert_dotenv(path: str, key: str, value: str, quote: bool = True):
    # keep simple: rewrite file preserving unrelated lines, update or append key
    lines = []
    found = False
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()

    out_lines = []
    for line in lines:
        m = ENV_LINE.match(line)
        if m and m.group(1) == key:
            found = True
            out_lines.append(f"{key}={_format_value(value, quote=quote)}")
        else:
            out_lines.append(line)

    if not found:
        if out_lines and out_lines[-1].strip() != "":
            out_lines.append("")
        out_lines.append(f"{key}={_format_value(value, quote=quote)}")

    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")


def _format_value(v: str, quote: bool) -> str:
    if not quote:
        return v
    # Always quote to avoid truncation/parse surprises (e.g. trailing ==)
    v = v.replace('"', '\\"')
    return f'"{v}"'


def getenv(env: Dict[str, str], key: str, default: Optional[str] = None) -> Optional[str]:
    return env.get(key) or os.environ.get(key) or default
