"""Neo4j vs FalkorDB: run the same role-based query pack on both engines over the SAME data and compare.

Library (used by the kit CLI and by the Cortex app) + CLI:
  python compare/aml_compare.py --manifest data/aml_full/manifest.json --falkordb-graph aml_full_v1 \
      --neo4j-uri neo4j://127.0.0.1:7687 --out artifacts/compare.json --html artifacts/compare.html
The Neo4j password is read from NEO4J_PASSWORD (prompted by the Makefile), never from arguments.
"""
import argparse
import html
import json
import math
import os
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_PACK = HERE / "aml_queries.json"


# ---------------------------------------------------------------- engines
class FalkorEngine:
    name = "FalkorDB"

    def __init__(self, graph_or_url, graph_name=None):
        if isinstance(graph_or_url, str):
            from falkordb import FalkorDB
            self.db = FalkorDB.from_url(graph_or_url)
            self.g = self.db.select_graph(graph_name)
        else:  # an already-selected graph object (Cortex)
            self.g, self.db = graph_or_url, None
        self.graph_name = graph_name

    def run(self, cypher, params):
        t = time.perf_counter()
        r = self.g.query(cypher, params)
        return [list(row) for row in r.result_set], (time.perf_counter() - t) * 1000, r.run_time_ms

    def write(self, cypher):
        self.g.query(cypher)

    def version(self):
        try:
            mods = self.g.client.execute_command("MODULE", "LIST") if hasattr(self.g, "client") else []
        except Exception:
            mods = []
        for m in mods or []:
            d = m if isinstance(m, dict) else dict(zip(m[::2], m[1::2]))
            d = {(k.decode() if isinstance(k, bytes) else k): v for k, v in d.items()}
            if d.get("name") == "graph":
                v = d.get("ver")
                return f"FalkorDB {v // 10000}.{v // 100 % 100}.{v % 100}" if isinstance(v, int) else f"FalkorDB {v}"
        return "FalkorDB"


class Neo4jEngine:
    name = "Neo4j"

    def __init__(self, uri, user, password, database="neo4j", driver=None):
        if driver is None:
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(uri, auth=(user, password), notifications_min_severity="OFF")
        self.driver, self.database = driver, database

    def run(self, cypher, params):
        t = time.perf_counter()
        with self.driver.session(database=self.database) as s:
            res = s.run(cypher, params)
            rows = [list(r.values()) for r in res]
            summ = res.consume()
        server = (summ.result_available_after or 0) + (summ.result_consumed_after or 0)
        return rows, (time.perf_counter() - t) * 1000, float(server)

    def write(self, cypher):
        with self.driver.session(database=self.database) as s:
            s.run(cypher).consume()

    def version(self):
        try:
            rows, _, _ = self.run("CALL dbms.components() YIELD name, versions, edition RETURN versions[0], edition", {})
            gds = ""
            try:
                gds = " + GDS " + self.run("RETURN gds.version()", {})[0][0][0]
            except Exception:
                pass
            return f"Neo4j {rows[0][0]} {rows[0][1]}{gds}"
        except Exception:
            return "Neo4j"


# ---------------------------------------------------------------- pack, params, indexes
def load_pack(path=DEFAULT_PACK):
    return json.loads(Path(path).read_text())


def _csv_id(data_dir, label, index):
    import csv as _csv
    path = Path(data_dir) / f"{label}.csv"
    if not path.exists():
        return None
    with open(path, newline="") as f:
        r = _csv.reader(f)
        next(r, None)
        for i, row in enumerate(r):
            if i == index:
                return row[0]
    return None


def resolve_params(pack, manifest, data_dir=None):
    """Parameters for the pack. Synthetic data: planted ring members. Real/extracted data: ids read from the CSVs."""
    rings = manifest.get("rings") or []
    members = [m for r in rings for m in r["members"]]
    out = {}
    for k, spec in pack.get("params", {}).items():
        if "value" in spec:
            out[k] = spec["value"]
            continue
        if spec.get("from") == "ring_member" and len(members) > spec["index"]:
            out[k] = members[spec["index"]]
            continue
        label = spec.get("label") or spec.get("fallback_label", "Customer")
        idx = spec.get("index", 0) if spec.get("from") == "node" else spec.get("fallback_index", spec.get("index", 0))
        n = manifest["nodes"].get(label, 0)
        out[k] = (_csv_id(data_dir, label, idx % max(1, n)) if data_dir else None) or f"{label}:{idx % max(1, n)}"
    return out


def create_indexes(engines, pack, log=print):
    for eng in engines:
        for label, prop in pack.get("indexes", []):
            stmt = f"CREATE INDEX FOR (n:`{label}`) ON (n.`{prop}`)"
            if eng.name == "Neo4j":
                stmt = f"CREATE INDEX cmp_{label}_{prop} IF NOT EXISTS FOR (n:`{label}`) ON (n.`{prop}`)"
            try:
                eng.write(stmt)
            except Exception as e:  # already exists on FalkorDB
                if "already" not in str(e).lower():
                    log(f"  {eng.name}: index {label}.{prop}: {e}")
        if eng.name == "Neo4j":
            eng.write("CALL db.awaitIndexes(600)")
        else:
            for _ in range(600):
                rows, _, _ = eng.run("CALL db.indexes() YIELD status RETURN collect(status)", {})
                if all(s == "OPERATIONAL" for s in rows[0][0]):
                    break
                time.sleep(0.5)


# ---------------------------------------------------------------- comparison
def _norm(v):
    if isinstance(v, float):
        return round(v, 6) if math.isfinite(v) else str(v)
    if isinstance(v, (list, tuple)):
        return [_norm(x) for x in v]
    return v


def agreement(kind, a_rows, b_rows):
    """Return (status, detail). status: match | mismatch | approx | overlap | n/a"""
    if a_rows is None or b_rows is None:
        return "n/a", "capability available in one engine only"
    if kind == "topk_overlap":
        a, b = {r[0] for r in a_rows}, {r[0] for r in b_rows}
        ov = len(a & b) / max(1, len(a | b) and max(len(a), len(b)))
        return ("overlap", f"top-{max(len(a), len(b))} overlap {len(a & b)}/{max(len(a), len(b))}") if ov < 1 else ("match", "identical top set")
    if kind == "info":
        return "info", f"{a_rows[0][0]} vs {b_rows[0][0]}: implementations differ, not expected to match"
    if kind == "approx":
        x, y = a_rows[0][0], b_rows[0][0]
        ok = abs(x - y) <= 0.05 * max(abs(x), abs(y), 1)
        return ("approx" if ok else "mismatch"), f"{x} vs {y} (within 5%: {'yes' if ok else 'no'})"
    na, nb = _norm(a_rows), _norm(b_rows)
    return ("match", f"{len(na)} identical row(s)") if na == nb else ("mismatch", f"{len(na)} vs {len(nb)} rows differ")


def _timed(eng, cypher, params, runs, warmup):
    rows, times, server = None, [], []
    for i in range(warmup + runs):
        rows, ms, srv = eng.run(cypher, params)
        if i >= warmup:
            times.append(ms)
            server.append(srv)
    return rows, {"runs": len(times), "p50_ms": round(statistics.median(times), 2), "min_ms": round(min(times), 2),
                  "max_ms": round(max(times), 2), "server_p50_ms": round(statistics.median(server), 2) if server else None}


def run_query(q, engines, params, runs=5, warmup=1):
    out = {"id": q["id"], "role": q["role"], "title": q["title"], "what": q["what"], "compare": q["compare"],
           "syntax_note": q.get("syntax_note"), "gap": q.get("gap"), "engines": {}}
    rows_by = {}
    for eng in engines:
        key = "cypher_neo4j" if eng.name == "Neo4j" else "cypher_falkordb"
        cypher = q.get(key, q.get("cypher"))
        res = {"cypher": cypher}
        if cypher is None:
            res["status"] = "not available"
            rows_by[eng.name] = None
            out["engines"][eng.name] = res
            continue
        try:
            if eng.name == "Neo4j" and q.get("neo4j_setup"):
                try:
                    eng.write(q["neo4j_teardown"])
                except Exception:
                    pass
                t = time.perf_counter()
                eng.write(q["neo4j_setup"])
                res["projection_ms"] = round((time.perf_counter() - t) * 1000, 2)
                res["setup"] = q["neo4j_setup"]
            rows, stats = _timed(eng, cypher, params, runs, warmup)
            res.update(stats, rows=_norm(rows[:25]), row_count=len(rows), status="ok")
            res["total_ms"] = round(stats["p50_ms"] + res.get("projection_ms", 0), 2)
            rows_by[eng.name] = rows
        except Exception as e:
            res.update(status="error", error=f"{type(e).__name__}: {str(e)[:300]}")
            rows_by[eng.name] = None
        finally:
            if eng.name == "Neo4j" and q.get("neo4j_teardown"):
                try:
                    eng.write(q["neo4j_teardown"])
                except Exception:
                    pass
        out["engines"][eng.name] = res
    names = [e.name for e in engines]
    if len(names) == 2:
        a, b = rows_by.get(names[0]), rows_by.get(names[1])
        if any(out["engines"][n]["status"] == "error" for n in names):
            out["agreement"], out["agreement_detail"] = "error", "see engine error"
        else:
            out["agreement"], out["agreement_detail"] = agreement(q["compare"], a, b)
        fa, nb = out["engines"].get("FalkorDB", {}), out["engines"].get("Neo4j", {})
        if fa.get("status") == "ok" and nb.get("status") == "ok":
            out["speedup"] = round(nb["total_ms"] / fa["total_ms"], 2) if fa["total_ms"] else None
    return out


def run_pack(engines, manifest, pack=None, roles=None, runs=5, warmup=1, log=print, data_dir=None):
    pack = pack or load_pack()
    params = resolve_params(pack, manifest, data_dir)
    for eng in engines:  # warm the JVM / GDS once so the first algorithm is not charged for start-up
        if eng.name == "Neo4j":
            try:
                eng.write("CALL gds.graph.project('cmp_warm', '*', '*') YIELD graphName RETURN graphName")
                eng.write("CALL gds.graph.drop('cmp_warm', false) YIELD graphName RETURN graphName")
            except Exception:
                pass
    results = []
    for q in pack["queries"]:
        if roles and q["role"] not in roles:
            continue
        r = run_query(q, engines, params, runs, warmup)
        results.append(r)
        e = r["engines"]
        log(f"  {q['id']:3} {q['title'][:46]:46} " + " · ".join(
            f"{n} {e[n].get('total_ms', e[n].get('status'))}" + (" ms" if e[n].get('status') == 'ok' else "") for n in e)
            + f" · {r.get('agreement')}")
    return {"pack": pack["name"], "pack_version": pack["version"], "roles": pack["roles"], "params": params,
            "engines": {e.name: e.version() for e in engines}, "runs": runs, "warmup": warmup,
            "dataset": {k: manifest.get(k) for k in ("model", "factor", "seed", "totals")},
            "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "results": results,
            "summary": summarise(results)}


def summarise(results):
    both = [r for r in results if r.get("speedup")]
    s = {"queries": len(results), "compared": len(both),
         "falkordb_faster": sum(1 for r in both if r["speedup"] > 1.05), "neo4j_faster": sum(1 for r in both if r["speedup"] < 0.95),
         "similar": sum(1 for r in both if 0.95 <= r["speedup"] <= 1.05),
         "answers_match": sum(1 for r in results if r.get("agreement") in ("match", "approx", "overlap")),
         "comparable": sum(1 for r in results if r.get("agreement") not in ("n/a", "info", "error")),
         "mismatches": [r["id"] for r in results if r.get("agreement") == "mismatch"],
         "neo4j_only": [r["id"] for r in results if r["engines"].get("FalkorDB", {}).get("status") == "not available"],
         "errors": [r["id"] for r in results if r.get("agreement") == "error"]}
    if both:
        s["median_speedup"] = round(statistics.median(r["speedup"] for r in both), 2)
    return s


# ---------------------------------------------------------------- HTML report (same layout as the Cortex tab)
def html_report(rep, platform=None):
    e = lambda x: html.escape(str(x))
    roles = {r["id"]: r for r in rep["roles"]}
    s = rep["summary"]
    rows = []
    for rid, role in roles.items():
        rows.append(f"<h2>{e(role['name'])}</h2><p class='sub'>{e(role['summary'])}</p>")
        for r in [x for x in rep["results"] if x["role"] == rid]:
            cells = []
            for name in ("Neo4j", "FalkorDB"):
                d = r["engines"].get(name, {})
                if d.get("status") == "ok":
                    proj = f"<div class='m'>+ projection {d['projection_ms']} ms</div>" if d.get("projection_ms") else ""
                    cells.append(f"<td><b>{d['p50_ms']} ms</b>{proj}<div class='m'>{d['row_count']} rows</div></td>")
                else:
                    cells.append(f"<td class='na'>{e(d.get('status', 'n/a'))}<div class='m'>{e(d.get('error', ''))}</div></td>")
            sp = f"{r['speedup']}×" if r.get("speedup") else "—"
            note = r.get("gap") or r.get("syntax_note") or ""
            rows.append(f"<table><tr><th style='width:34%'>{e(r['id'])} · {e(r['title'])}<div class='m'>{e(r['what'])}</div></th>{''.join(cells)}"
                        f"<td><b>{sp}</b><div class='m'>FalkorDB vs Neo4j (total)</div></td><td class='{e(r.get('agreement'))}'>{e(r.get('agreement'))}<div class='m'>{e(r.get('agreement_detail', ''))}</div></td></tr>"
                        + (f"<tr><td colspan='5' class='m'>{e(note)}</td></tr>" if note else "") + "</table>")
    plat = ""
    if platform:
        plat = "<h2>Platform</h2><table>" + "".join(f"<tr><th>{e(k)}</th><td>{e(v)}</td></tr>" for k, v in platform.items()) + "</table>"
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Neo4j vs FalkorDB</title><style>
body{{font-family:Arial,Helvetica,sans-serif;max-width:1150px;margin:24px auto;padding:0 16px;color:#0f172a}}
h1{{border-bottom:3px solid #F97316;padding-bottom:6px}}h2{{color:#0B1B3A;margin-top:26px}}.sub{{color:#475569}}
table{{width:100%;border-collapse:collapse;margin:6px 0}}th,td{{border:1px solid #e2e8f0;padding:7px;vertical-align:top;text-align:left;font-size:13px}}
th{{background:#f8fafc}}.m{{color:#64748b;font-size:11.5px;font-weight:normal}}.match,.approx,.overlap{{color:#047857}}.mismatch,.error{{color:#b91c1c}}.na,.n\\/a{{color:#92400e}}
.kpi{{display:inline-block;background:#fff7ed;border-radius:10px;padding:10px 14px;margin:4px 8px 4px 0}}.kpi b{{font-size:22px;color:#0B1B3A}}</style></head><body>
<h1>{e(rep['pack'])}</h1>
<p class='sub'>{e(rep['engines'])} · dataset {e(rep['dataset'].get('model'))} factor {e(rep['dataset'].get('factor'))}: {e(rep['dataset'].get('totals'))} · p50 of {rep['runs']} warm runs (client round trip) · {e(rep['finished_at'])}</p>
<div><span class='kpi'><b>{s.get('median_speedup', '—')}×</b><br>median speed-up (FalkorDB vs Neo4j)</span>
<span class='kpi'><b>{s['falkordb_faster']}</b> / {s['compared']}<br>queries faster on FalkorDB</span>
<span class='kpi'><b>{s['answers_match']}</b> / {s['comparable']}<br>comparable answers agree</span>
<span class='kpi'><b>{len(s['neo4j_only'])}</b><br>Neo4j-only capabilities</span></div>
{plat}{''.join(rows)}
<p class='m'>Same CSV files loaded into both engines; same indexes; Cypher identical unless a syntax note says otherwise. Neo4j GDS algorithms need an in-memory projection, timed separately and included in the total. Numbers describe this machine and data shape only.</p>
</body></html>"""


# ---------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--pack", default=str(DEFAULT_PACK))
    ap.add_argument("--falkordb-url", default=os.getenv("FALKORDB_URL", "redis://127.0.0.1:6379"))
    ap.add_argument("--falkordb-graph", required=True)
    ap.add_argument("--neo4j-uri", default=os.getenv("NEO4J_COMPARE_URI", "neo4j://127.0.0.1:7687"))
    ap.add_argument("--neo4j-user", default=os.getenv("NEO4J_COMPARE_USER", "neo4j"))
    ap.add_argument("--neo4j-database", default=os.getenv("NEO4J_COMPARE_DATABASE", "neo4j"))
    ap.add_argument("--roles", help="comma-separated role ids (default: all)")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--no-indexes", action="store_true", help="skip creating the pack's indexes")
    ap.add_argument("--out", required=True)
    ap.add_argument("--html")
    ap.add_argument("--platform", help="JSON file with platform facts to include (load times, memory)")
    a = ap.parse_args()
    pwd = os.getenv("NEO4J_PASSWORD")
    if not pwd:
        sys.exit("Set NEO4J_PASSWORD (the Makefile prompts for it).")
    manifest = json.loads(Path(a.manifest).read_text())
    pack = load_pack(a.pack)
    engines = [Neo4jEngine(a.neo4j_uri, a.neo4j_user, pwd, a.neo4j_database), FalkorEngine(a.falkordb_url, a.falkordb_graph)]
    if not a.no_indexes:
        print("Creating the same indexes on both engines and waiting until they are online")
        create_indexes(engines, pack)
    print(f"Running {pack['name']} ({len(pack['queries'])} queries)")
    rep = run_pack(engines, manifest, pack, a.roles.split(",") if a.roles else None, a.runs, data_dir=Path(a.manifest).parent)
    platform = json.loads(Path(a.platform).read_text()) if a.platform else None
    rep["platform"] = platform
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(rep, indent=2, default=str))
    if a.html:
        Path(a.html).write_text(html_report(rep, platform))
    s = rep["summary"]
    print(f"\nFalkorDB faster on {s['falkordb_faster']}/{s['compared']} · median speed-up {s.get('median_speedup')}× · "
          f"answers agree {s['answers_match']}/{s['comparable']} · Neo4j-only: {s['neo4j_only']} · mismatches: {s['mismatches']} · errors: {s['errors']}")
    print(f"Report: {a.out}" + (f" · {a.html}" if a.html else ""))
    if s["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
