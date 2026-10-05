"""Cortex comparison service: generic AML synthetic data -> FalkorDB and Neo4j (same CSVs) -> role-based queries.

Runs in its own background thread after the main app is ready, so GraphRAG and the other tabs are not delayed by
Neo4j downloads. State lives in COMPARE (read by /api/compare). Individual queries can be re-run live.
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import aml_compare as cmp  # noqa: E402

GRAPH = "cmp_aml"
DATA = Path(os.getenv("CORTEX_CMP_DATA", "/tmp/cortex-aml"))
PACK = HERE / "generic_aml_queries.json"
MODEL = HERE / "generic_aml.model.json"
COMPARE = {"phase": "waiting", "ready": False, "log": [], "report": None, "error": None, "platform": {},
           "live": {}, "neo4j_available": False}
LOCK = threading.Lock()
_engines = {}
_last_run = {}


def log(msg):
    COMPARE["phase"] = msg
    COMPARE["log"].append(f"{time.strftime('%H:%M:%S')} {msg}")
    print("[compare]", msg, flush=True)


def _factor():
    return float(os.getenv("CORTEX_CMP_FACTOR", "1"))


def _load_falkordb(manifest):
    from core.graph import db
    if GRAPH in set(db().list_graphs()):
        return None
    exe = shutil.which("falkordb-bulk-insert") or str(Path(sys.executable).parent / "falkordb-bulk-insert")
    cmd = [exe, GRAPH, "--server-url", "redis://127.0.0.1:6379", "--enforce-schema", "--max-buffer-size", "16"]
    for f in manifest["files"]:
        cmd += ["-n" if f["kind"] == "node" else "-r", str(DATA / f["file"])]
    t = time.perf_counter()
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    return round(time.perf_counter() - t, 2)


def build():
    try:
        import generate_seed
        model = json.loads(MODEL.read_text())
        if not (DATA / "manifest.json").exists():
            log(f"Generating generic AML data (factor {_factor()})")
            if DATA.exists():
                shutil.rmtree(DATA)
            generate_seed.generate(model, _factor(), DATA)
        manifest = json.loads((DATA / "manifest.json").read_text())
        log(f"Loading {manifest['totals']['entities']:,} entities into FalkorDB (GRAPH.BULK)")
        f_secs = _load_falkordb(manifest)
        from core.graph import db
        falkor = cmp.FalkorEngine(db().select_graph(GRAPH), GRAPH)
        _engines["FalkorDB"] = falkor
        neo = None
        try:
            import neo4j_embedded as ne
            log("Installing Neo4j Community + GDS (first start downloads ~230 MB)")
            root = ne.install(log)
            log("Importing the same CSVs into Neo4j (neo4j-admin import)")
            n_imp = ne.import_csvs(root, DATA, manifest, log)
            log("Starting Neo4j")
            neo = cmp.Neo4jEngine(None, None, None, driver=ne.start(root, log))
            _engines["Neo4j"] = neo
            COMPARE["neo4j_available"] = True
            mem = None
            try:
                r = db().connection.execute_command("GRAPH.MEMORY", "USAGE", GRAPH)
                mem = dict(zip(r[::2], r[1::2])).get("total_graph_sz_mb")
            except Exception:
                pass
            sb = ne.store_bytes(root)
            COMPARE["platform"] = {
                "Dataset": f"{manifest['totals']['nodes']:,} nodes + {manifest['totals']['relationships']:,} relationships (generic AML, seed {manifest['seed']})",
                "CSV size": f"{sum(f['bytes'] for f in manifest['files']) / 1e6:,.1f} MB (identical files for both engines)",
                "FalkorDB load (GRAPH.BULK)": f"{f_secs} s" if f_secs else "already loaded",
                "Neo4j load (neo4j-admin import)": f"{n_imp['reported']} (peak {n_imp['peak_memory']})",
                "FalkorDB graph memory": f"{mem} MB" if mem is not None else "n/a",
                "Neo4j store on disk": f"{sb / 1e6:,.1f} MB + heap {os.getenv('CORTEX_NEO4J_HEAP', '1g')} / page cache {os.getenv('CORTEX_NEO4J_PAGECACHE', '768m')}" if sb else "n/a",
            }
        except Exception as e:
            COMPARE["error"] = f"Neo4j unavailable in this container: {type(e).__name__}: {str(e)[:300]}"
            log(COMPARE["error"])
        engines = [e for e in (neo, falkor) if e]
        pack = json.loads(PACK.read_text())
        log("Creating the same indexes on both engines")
        cmp.create_indexes(engines, pack, log=log)
        log("Running every role's queries on both engines")
        with LOCK:
            rep = cmp.run_pack(engines, manifest, pack, runs=3, warmup=1, log=lambda m: None, data_dir=DATA)
        rep["platform"] = COMPARE["platform"]
        COMPARE["report"] = rep
        COMPARE["ready"] = True
        log("Ready")
    except Exception as e:
        COMPARE["error"] = f"{type(e).__name__}: {e}"
        log(f"Comparison failed: {COMPARE['error']}")


def start_background():
    threading.Thread(target=build, daemon=True).start()


def run_live(qid):
    """Re-run one query on both engines now (cooldown 15 s per query; one run at a time)."""
    rep = COMPARE.get("report")
    if not rep:
        raise RuntimeError("Comparison still warming up")
    pack = json.loads(PACK.read_text())
    q = next((x for x in pack["queries"] if x["id"] == qid), None)
    if not q:
        raise KeyError(qid)
    if time.time() - _last_run.get(qid, 0) < 15 and qid in COMPARE["live"]:
        return COMPARE["live"][qid]
    if not LOCK.acquire(timeout=60):
        raise RuntimeError("Another live run is in progress")
    try:
        engines = [e for e in (_engines.get("Neo4j"), _engines.get("FalkorDB")) if e]
        r = cmp.run_query(q, engines, rep["params"], runs=3, warmup=1)
        r["ran_at"] = time.strftime("%H:%M:%S UTC", time.gmtime())
        COMPARE["live"][qid] = r
        _last_run[qid] = time.time()
        return r
    finally:
        LOCK.release()
