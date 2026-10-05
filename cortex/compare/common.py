"""Shared helpers. Standard library only at import time, so unit tests run without any installed packages."""
import datetime as _dt
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "artifacts"


def load_env(path=ROOT / ".env"):
    """Minimal .env reader (KEY=VALUE, # comments). Existing environment variables win."""
    if not Path(path).exists():
        return
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def now():
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")
    return path


def read_json(path):
    return json.loads(Path(path).read_text())


def ok(msg):
    print(f"  PASS  {msg}", flush=True)


def warn(msg):
    print(f"  WARN  {msg}", flush=True)


def bad(msg):
    print(f"  FAIL  {msg}", flush=True)


def die(msg, code=1):
    print(f"\nSTOP: {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


def falkordb_url():
    load_env()
    return os.getenv("FALKORDB_URL", "redis://127.0.0.1:6379")


def falkor():
    """Connected FalkorDB client (lazy import so tests need no packages)."""
    from falkordb import FalkorDB
    return FalkorDB.from_url(falkordb_url())


def graph_keys(db):
    return set(db.connection.execute_command("GRAPH.LIST") or [])


def key_exists(db, name):
    return bool(db.connection.exists(name))


def schema_objects(g):
    """Indexes and constraints currently defined on a graph, with their states."""
    def rows(q):
        r = g.ro_query(q)
        hdr = [c[1] if isinstance(c, (list, tuple)) else c for c in r.header]
        return [dict(zip(hdr, row)) for row in r.result_set]
    return rows("CALL db.indexes()"), rows("CALL db.constraints()")


def redis_memory(db):
    i = db.connection.info("memory")
    return {k: i.get(k) for k in ("used_memory", "used_memory_human", "used_memory_peak", "used_memory_peak_human",
                                  "used_memory_rss", "used_memory_rss_human")}


class Timer:
    def __enter__(self):
        self.t = time.perf_counter()
        return self

    def __exit__(self, *a):
        self.s = time.perf_counter() - self.t
