"""Run Neo4j Community + GDS inside the Cortex container (no Docker on Hugging Face Spaces).

Downloads the official tarball and GDS jar once (cached under CORTEX_NEO4J_HOME), imports the comparison CSVs with
neo4j-admin (offline, the same files FalkorDB loaded), then starts the server on 127.0.0.1 only. Java comes from
packages.txt (openjdk-17-jre-headless). Licences: Neo4j Community and GDS Community are GPLv3; used unmodified.
"""
import os
import re
import secrets
import shutil
import subprocess
import tarfile
import time
import urllib.request
from pathlib import Path

NEO4J_VERSION = os.getenv("CORTEX_NEO4J_VERSION", "5.26.31")
GDS_VERSION = os.getenv("CORTEX_GDS_VERSION", "2.13.13")
HOME = Path(os.getenv("CORTEX_NEO4J_HOME", "/tmp/cortex-neo4j"))
BOLT_PORT = int(os.getenv("CORTEX_NEO4J_BOLT_PORT", "7687"))


def _download(url, dest, log):
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    log(f"Downloading {url.rsplit('/', 1)[-1]}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=300) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)
    tmp.rename(dest)
    return dest


def install(log=print):
    if not shutil.which("java"):
        raise RuntimeError("Java not found (packages.txt must install openjdk-17-jre-headless)")
    HOME.mkdir(parents=True, exist_ok=True)
    root = HOME / f"neo4j-community-{NEO4J_VERSION}"
    if not (root / "bin" / "neo4j").exists():
        tgz = _download(f"https://dist.neo4j.org/neo4j-community-{NEO4J_VERSION}-unix.tar.gz", HOME / f"neo4j-{NEO4J_VERSION}.tgz", log)
        with tarfile.open(tgz) as t:
            t.extractall(HOME)
    jar = root / "plugins" / f"neo4j-graph-data-science-{GDS_VERSION}.jar"
    _download(f"https://graphdatascience.ninja/neo4j-graph-data-science-{GDS_VERSION}.jar", jar, log)
    conf = root / "conf" / "neo4j.conf"
    text = conf.read_text()
    extra = {
        "server.default_listen_address": "127.0.0.1",
        "server.bolt.listen_address": f"127.0.0.1:{BOLT_PORT}",
        "server.http.enabled": "false",
        "server.https.enabled": "false",
        "server.memory.heap.initial_size": os.getenv("CORTEX_NEO4J_HEAP", "1g"),
        "server.memory.heap.max_size": os.getenv("CORTEX_NEO4J_HEAP", "1g"),
        "server.memory.pagecache.size": os.getenv("CORTEX_NEO4J_PAGECACHE", "768m"),
        "dbms.security.procedures.unrestricted": "gds.*",
        "dbms.usage_report.enabled": "false",
    }
    for k, v in extra.items():
        text = re.sub(rf"^#?\s*{re.escape(k)}=.*$", "", text, flags=re.M)
        text += f"\n{k}={v}"
    conf.write_text(text)
    return root


def import_csvs(root, data_dir, manifest, log=print):
    args = [str(root / "bin" / "neo4j-admin"), "database", "import", "full", "neo4j", "--overwrite-destination=true", f"--report-file={HOME / 'import.report'}"]
    for f in manifest["files"]:
        args.append(("--nodes" if f["kind"] == "node" else "--relationships") + f"={f['name']}={Path(data_dir) / f['file']}")
    t = time.perf_counter()
    p = subprocess.run(args, capture_output=True, text=True)
    out = p.stdout + p.stderr
    if "IMPORT DONE" not in out:
        raise RuntimeError("neo4j-admin import failed: " + out[-600:])
    m = re.search(r"IMPORT DONE in ([^\n]+)", out)
    peak = re.search(r"Peak memory usage: ([^\n]+)", out)
    return {"seconds": round(time.perf_counter() - t, 2), "reported": m.group(1).strip().rstrip(".") if m else None,
            "peak_memory": peak.group(1).strip() if peak else None}


def start(root, log=print):
    """Set a random password (container-local, never shown), start the server, return (driver, password)."""
    pwd = secrets.token_urlsafe(18)
    auth = root / "data" / "dbms" / "auth.ini"
    if not auth.exists():
        subprocess.run([str(root / "bin" / "neo4j-admin"), "dbms", "set-initial-password", pwd], capture_output=True, check=True)
    else:
        pwd = (HOME / ".pw").read_text().strip()
    (HOME / ".pw").write_text(pwd)
    logf = open(HOME / "neo4j.log", "a")
    subprocess.Popen([str(root / "bin" / "neo4j"), "console"], stdout=logf, stderr=subprocess.STDOUT)
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(f"neo4j://127.0.0.1:{BOLT_PORT}", auth=("neo4j", pwd), notifications_min_severity="OFF")
    for _ in range(240):
        try:
            driver.verify_connectivity()
            with driver.session() as s:
                s.run("RETURN 1").consume()
            log("Neo4j started")
            return driver
        except Exception:
            time.sleep(1)
    raise RuntimeError("Neo4j did not start; see " + str(HOME / "neo4j.log"))


def store_bytes(root):
    d = root / "data" / "databases" / "neo4j"
    return sum(p.stat().st_size for p in d.rglob("*") if p.is_file()) if d.exists() else None
