"""One-click demo scenarios. All pure Cypher on FalkorDB: no LLM, no tokens, no cost."""
import json
import statistics
from pathlib import Path

from core.graph import KG, OPS, graph
from core.retrieval import allowed_docs, visible

ROOT = Path(__file__).resolve().parent.parent
FRAUD_ROLES = {"ROLE-COMPLIANCE", "ROLE-CRO", "ROLE-AUDITOR"}
SCORE = {"Green": 100, "Amber": 60, "Breach": 20}


def _run(g, q, params=None):
    r = g.query(q, params or {})
    return r.result_set, round(float(r.run_time_ms), 2)


FRAUD_CYPHER = """MATCH (d:Device)<-[:USES_DEVICE]-(c:Customer)
WITH d, collect(DISTINCT c) AS members WHERE size(members) >= 5
UNWIND members AS c1
MATCH (c1)-[:OWNS]->(a1:Account)-[t:TRANSFER]->(a2:Account)<-[:OWNS]-(c2:Customer)-[:USES_DEVICE]->(d)
WHERE t.amount >= 9000 AND t.amount < 10000
WITH d, members, count(t) AS links WHERE links >= 3
RETURN d.id, [m IN members | m.id], links ORDER BY links DESC"""


def fraud(role):
    if role not in FRAUD_ROLES:
        return {"denied": True, "message": "Fraud-ring alerts are L3 Restricted (Compliance, CRO, Internal Audit only)."}
    rows, ms = _run(graph(OPS), FRAUD_CYPHER)
    rings = [{"device": d, "customers": m, "suspicious_transfers": n} for d, m, n in rows]
    gold_path = ROOT / "data" / "ops_gold.json"
    score = None
    if gold_path.exists():
        gold = {g["shared_device"] for g in json.loads(gold_path.read_text())}
        found = {r["device"] for r in rings}
        score = {"planted": len(gold), "detected": len(found & gold), "false_alarms": len(found - gold),
                 "recall": round(len(found & gold) / max(1, len(gold)), 3)}
    nodes = graph(OPS).query("MATCH (n) RETURN count(n)").result_set[0][0]
    return {"rings": rings[:25], "total": len(rings), "ms": ms, "graph_nodes": nodes, "score": score, "cypher": FRAUD_CYPHER}


ROLLUP_CYPHER = """MATCH (f:Document)-[:DEFINES]->(k:Entity)
OPTIONAL MATCH (k)-[:MEASURES]->(c:Entity)
WITH f, k, collect(DISTINCT c.id) AS ctls
OPTIONAL MATCH (k)-[:MEASURES]->(:Entity)<-[:RAISED_ON]-(af:Entity)
RETURN f.id, f.title, f.dept, k.id, k.name, k.status, k.current, k.target, ctls, collect(DISTINCT af.id)"""


def rollup(role):
    allowed = allowed_docs(role)
    rows, ms = _run(graph(KG), ROLLUP_CYPHER)
    frameworks = {}
    for fid, title, dept, kid, kname, status, cur, tgt, ctls, findings in rows:
        if not visible(kid, allowed):
            continue
        fw = frameworks.setdefault(fid, {"framework": fid, "title": title, "dept": dept, "kris": []})
        fw["kris"].append({"id": kid, "name": kname, "status": status, "current": cur, "target": tgt, "controls": ctls,
                           "findings": [f for f in findings if visible(f, allowed)]})
    for fw in frameworks.values():
        fw["score"] = round(statistics.mean(SCORE.get(k["status"], 50) for k in fw["kris"]))
    all_kris = [k for fw in frameworks.values() for k in fw["kris"]]
    bank = round(statistics.mean(SCORE.get(k["status"], 50) for k in all_kris)) if all_kris else None
    return {"bank_score": bank, "frameworks": list(frameworks.values()), "ms": ms, "cypher": ROLLUP_CYPHER,
            "note": None if all_kris else "No KRI frameworks are visible to this role."}


VERSIONS_CYPHER = """MATCH (cur:Document)-[:SUPERSEDES]->(old:Document)
RETURN cur.id, cur.title, cur.version, cur.effective, old.id, old.title, old.version, old.effective ORDER BY old.effective"""


def versions(role):
    allowed = allowed_docs(role)
    rows, ms = _run(graph(KG), VERSIONS_CYPHER)
    return {"chains": [{"current": {"id": a, "title": b, "version": c, "effective": d},
                        "retired": {"id": e, "title": f, "version": g, "effective": h}}
                       for a, b, c, d, e, f, g, h in rows if visible(a, allowed)], "ms": ms, "cypher": VERSIONS_CYPHER}


PERF = [
    ("Point lookup: one account", OPS, "MATCH (a:Account {id:'A12345'}) RETURN a"),
    ("2-hop: customer -> accounts -> counterparties", OPS, "MATCH (c:Customer {id:'C777'})-[:OWNS]->(:Account)-[:TRANSFER]->(b:Account) RETURN count(b)"),
    ("4-hop: money trail from one account", OPS, "MATCH (a:Account {id:'A42'})-[:TRANSFER*1..4]->(b:Account) RETURN count(DISTINCT b)"),
    ("Aggregation: transfers >= 9,000 by branch", OPS, "MATCH (a:Account)-[t:TRANSFER]->() WHERE t.amount >= 9000 RETURN a.branch, count(t) ORDER BY count(t) DESC LIMIT 5"),
    ("Regulatory impact (5 joins)", KG, "MATCH (r:Entity {id:'REG-EUAI'})<-[:IMPLEMENTS]-(p)-[:HAS_CONTROL]->(c) OPTIONAL MATCH (k)-[:MEASURES]->(c) OPTIONAL MATCH (f)-[:RAISED_ON]->(c) RETURN p.id, c.id, k.id, f.id"),
    ("Vector search: top 10 similar chunks", KG, None),
]


def perf(runs=5):
    from core.embeddings import LocalEmbeddings
    v = LocalEmbeddings().embed_query("customer due diligence for politically exposed persons")
    out = []
    for name, gname, q in PERF:
        g = graph(gname)
        params = {}
        if q is None:
            q, params = "CALL db.idx.vector.queryNodes('Chunk','embedding',10,vecf32($v)) YIELD node RETURN node.id", {"v": v}
        times = [_run(g, q, params)[1] for _ in range(runs)]
        out.append({"query": name, "graph": gname, "median_ms": round(statistics.median(times[1:] or times), 2), "cypher": q})
    counts = {gname: graph(gname).query("MATCH (n) RETURN count(n)").result_set[0][0] for gname in (OPS, KG)}
    return {"queries": out, "graph_sizes": counts, "note": "FalkorDB internal execution time, median of warm runs."}


def neighborhood(center, role, graph_name=KG, limit=60):
    allowed = allowed_docs(role, graph_name)
    rows = graph(graph_name).query(
        "MATCH (s:Entity {id:$id})-[r]-(m:Entity) RETURN s.id, coalesce(s.name, s.title), s.kind, type(r), "
        "startNode(r).id, m.id, coalesce(m.name, m.title), m.kind LIMIT 300", {"id": center}).result_set
    nodes, edges = {}, []
    for sid, sname, skind, rel, start, mid, mname, mkind in rows:
        if not (visible(sid, allowed) and visible(mid, allowed)):
            continue
        nodes[sid] = {"id": sid, "label": sname or sid, "kind": skind}
        nodes[mid] = {"id": mid, "label": mname or mid, "kind": mkind}
        edges.append({"source": start, "target": mid if start == sid else sid, "rel": rel})
        if len(edges) >= limit:
            break
    return {"nodes": list(nodes.values()), "edges": edges}
