"""X-Ray: live introspection of the running FalkorDB engine and the Cortex stack."""
import time

from core.graph import KG, OPS, SANDBOX_PREFIX, db, graph
from core.retrieval import GRAPH_CYPHER, IMPACT_CYPHER
from core.scenarios import FRAUD_CYPHER

CONFIG_KEYS = ("THREAD_COUNT", "OMP_THREAD_COUNT", "CACHE_SIZE", "NODE_CREATION_BUFFER", "DELTA_MAX_PENDING_CHANGES",
               "VKEY_MAX_ENTITY_COUNT", "BOLT_PORT")
PLAN_QUERIES = {
    "graphrag": ("GraphRAG retrieval (2-hop expansion from seed entities)", KG, GRAPH_CYPHER, {"seeds": ["REG-EUAI", "POL-AI-001"]}),
    "impact": ("Regulatory impact (staged multi-hop aggregation)", KG, IMPACT_CYPHER, {"reg": "REG-EUAI"}),
    "vector": ("Vector search (HNSW index inside the same engine)", KG,
               "CALL db.idx.vector.queryNodes('Chunk', 'embedding', 6, vecf32($v)) YIELD node, score RETURN node.doc_id, score", None),
    "fraud": ("Fraud rings: shared devices across 1M+ nodes", OPS, FRAUD_CYPHER, {}),
}


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _ver(v):
    return f"{v // 10000}.{v // 100 % 100}.{v % 100}" if isinstance(v, int) else str(v)


def _graph_info(name):
    g = graph(name)
    q = lambda c: g.query(c).result_set
    labels = [r[0] for r in _safe(lambda: q("CALL db.labels()"), [])]
    rels = [r[0] for r in _safe(lambda: q("CALL db.relationshipTypes()"), [])]
    counts = {l: _safe(lambda: q(f"MATCH (n:`{l}`) RETURN count(n)")[0][0], 0) for l in labels}
    rel_counts = {r: _safe(lambda: q(f"MATCH ()-[e:`{r}`]->() RETURN count(e)")[0][0], 0) for r in rels}
    idx = _safe(lambda: q("CALL db.indexes() YIELD label, properties, types RETURN label, properties, types"), [])
    mem = _safe(lambda: db().connection.execute_command("GRAPH.MEMORY", "USAGE", name))
    if isinstance(mem, list):
        mem = dict(zip(mem[::2], mem[1::2]))
    return {"name": name, "nodes": sum(counts.values()), "edges": sum(rel_counts.values()),
            "labels": counts, "relationships": rel_counts,
            "indexes": [{"label": l, "properties": p, "types": t} for l, p, t in idx], "memory": mem}


def overview():
    c = db().connection
    info = _safe(c.info, {})
    mods = _safe(lambda: c.execute_command("MODULE", "LIST"), [])
    mods = [dict(zip(m[::2], m[1::2])) for m in mods]
    fk = next((m for m in mods if m.get("name") == "graph"), {})
    cfg = dict(_safe(lambda: c.execute_command("GRAPH.CONFIG", "GET", "*"), []))
    graphs = _safe(lambda: c.execute_command("GRAPH.LIST"), [])
    t = time.perf_counter()
    main = [_graph_info(g) for g in (KG, OPS) if g in graphs]
    return {"engine": {"falkordb": _ver(fk.get("ver")), "redis": info.get("redis_version"),
                       "memory": info.get("used_memory_human"), "peak_memory": info.get("used_memory_peak_human"),
                       "uptime_min": round(info.get("uptime_in_seconds", 0) / 60), "clients": info.get("connected_clients"),
                       "modules": [m.get("name") for m in mods]},
            "config": {k: cfg.get(k) for k in CONFIG_KEYS},
            "graphs": main, "sandboxes": sum(1 for g in graphs if g.startswith(SANDBOX_PREFIX)),
            "introspection_ms": round((time.perf_counter() - t) * 1000, 1)}


def plan(name):
    """Real GRAPH.EXPLAIN (compiled plan) and GRAPH.PROFILE (per-operator records and time)."""
    title, gname, cypher, params = PLAN_QUERIES[name]
    g = graph(gname)
    if params is None:  # vector: use a stored chunk embedding as the probe
        v = g.query("MATCH (c:Chunk) RETURN c.embedding LIMIT 1").result_set[0][0]
        params = {"v": list(v)}
    explain = "\n".join(g.explain(cypher, params).plan)
    t = time.perf_counter()
    profile = _safe(lambda: "\n".join(g.profile(cypher, params).plan), "")
    ms = round((time.perf_counter() - t) * 1000, 1)
    shown = {k: (f"[{len(v)} floats]" if k == "v" else v) for k, v in params.items()}
    return {"title": title, "graph": gname, "cypher": cypher, "params": shown, "explain": explain, "profile": profile, "ms": ms}
