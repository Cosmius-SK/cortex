"""Generate and bulk-load the operational graph into FalkorDB."""
import subprocess
import sys
from pathlib import Path

from core.graph import OPS, graph

ROOT = Path(__file__).resolve().parent.parent
FILES = ["Branch", "Customer", "Account", "Device", "Address", "IP", "Merchant"]
RELS = ["OWNS", "USES_DEVICE", "LIVES_AT", "LOGGED_FROM", "TRANSFER", "PAID"]


def load_ops(scale=1.0, url="redis://localhost:6379"):
    subprocess.run([sys.executable, "-m", "generator.ops_data", "--scale", str(scale)], cwd=ROOT, check=True)
    try:
        graph(OPS).delete()
    except Exception:
        pass
    ops = ROOT / "data" / "ops"
    cmd = ["falkordb-bulk-insert", OPS, "-u", url, "-b", "8", "-c", "256"]
    for f in FILES:
        cmd += ["-n", str(ops / f"{f}.csv")]
    for r in RELS:
        cmd += ["-r", str(ops / f"{r}.csv")]
    bindir = Path(sys.executable).parent
    cmd[0] = str(bindir / cmd[0]) if (bindir / cmd[0]).exists() else cmd[0]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    g = graph(OPS)
    for label in ("Customer", "Account", "Device", "Address"):
        g.query(f"CREATE INDEX FOR (n:{label}) ON (n.id)")
    # Indexes build in the background; wait until lookups use them so first measurements are fair.
    import time
    for _ in range(120):
        if g.query("MATCH (a:Account {id:'A1'}) RETURN a").run_time_ms < 5:
            break
        time.sleep(1)


if __name__ == "__main__":
    load_ops(float(sys.argv[1]) if len(sys.argv) > 1 else 1.0)
