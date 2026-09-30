"""Cold start: launch FalkorDB (embedded if no server is reachable), then build both graphs."""
import os
import subprocess
import threading
import time
from pathlib import Path

STATUS = {"ready": False, "phase": "starting", "log": [], "started": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
          "ops_scale": None, "ram_gb": None}


def log(msg):
    STATUS["phase"] = msg
    STATUS["log"].append(f"{time.strftime('%H:%M:%S')} {msg}")
    print(msg, flush=True)


def _reachable():
    try:
        from core.graph import db
        db().connection.ping()
        return True
    except Exception:
        return False


def _embedded_binaries():
    """redis-server + falkordb.so shipped inside the falkordblite wheel, or FALKOR_BIN_DIR."""
    d = os.getenv("FALKOR_BIN_DIR")
    if d:
        return Path(d) / "redis-server", Path(d) / "falkordb.so"
    import redislite
    b = Path(redislite.__file__).parent / "bin"
    return b / "redis-server", b / "falkordb.so"


def start_falkordb():
    if _reachable():
        log("FalkorDB server found")
        return
    server, module = _embedded_binaries()
    data = Path(os.getenv("FALKOR_DATA", "/tmp/falkordb"))
    data.mkdir(parents=True, exist_ok=True)
    subprocess.Popen([str(server), "--port", "6379", "--bind", "127.0.0.1", "--save", "", "--appendonly", "no",
                      "--dir", str(data), "--loadmodule", str(module)], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    from core.graph import db
    db.cache_clear()
    for _ in range(60):
        if _reachable():
            log("Embedded FalkorDB started")
            return
        time.sleep(0.5)
    raise RuntimeError("FalkorDB did not start")


def ops_scale():
    if os.getenv("CORTEX_OPS_SCALE"):
        return float(os.getenv("CORTEX_OPS_SCALE"))
    try:
        import psutil
        gb = psutil.virtual_memory().total / 1e9
    except Exception:
        gb = 8
    STATUS["ram_gb"] = round(gb, 1)
    return 1.0 if gb >= 12 else 0.5 if gb >= 6 else 0.2


def build():
    try:
        start_falkordb()
        from core.graph import KG, OPS, db
        existing = set(db().list_graphs())
        if os.getenv("CORTEX_REBUILD") or KG not in existing:
            log("Building knowledge graph from 73 PDFs (LangChain + embeddings)")
            from ingest.pipeline import build_kg
            build_kg()
        if os.getenv("CORTEX_REBUILD") or OPS not in existing:
            scale = ops_scale()
            STATUS["ops_scale"] = scale
            log(f"Generating and loading operational graph (scale {scale})")
            from ingest.load_ops import load_ops
            load_ops(scale)
        from core.scenarios import perf
        STATUS["perf"] = perf(runs=3)  # warms caches; cached for the overview tiles
        log("Ready")
        STATUS["ready"] = True
    except Exception as e:  # surface the failure on the status page instead of crashing silently
        log(f"Startup failed: {type(e).__name__}: {e}")


def start_background():
    threading.Thread(target=build, daemon=True).start()

