"""Vector RAG vs GraphRAG over the same FalkorDB graph, with role-aware access control.

Both modes use the same chunks, embeddings, LLM and prompt. Only retrieval differs:
  vector : top-k similar chunks
  graph  : top-k similar chunks as entry points + typed multi-hop expansion over the knowledge graph
Content the selected role may not see is filtered out before anything reaches the LLM.
"""
import re
import time
from functools import lru_cache

from core.embeddings import LocalEmbeddings
from core.graph import KG, graph
from ingest.pipeline import ID_RE

EXPAND_RELS = "IMPLEMENTS|HAS_CONTROL|MITIGATES|USES_SYSTEM|SUPERSEDES|APPLIES_TO|DEFINES|MEASURES|RAISED|RAISED_ON|CONCERNS|IMPACTS|ADDRESSES"
_emb = LocalEmbeddings()


@lru_cache(maxsize=64)
def allowed_docs(role, graph_name=KG):
    g = graph(graph_name)
    if not role or graph_name != KG:
        return None  # sandbox graphs belong to the uploader: no role filter
    return {r[0] for r in g.query("MATCH (:Role {id:$r})-[:CAN_ACCESS]->(d:Document) RETURN d.id", {"r": role}).result_set}


@lru_cache(maxsize=1)
def _parents():
    """Findings/KRIs inherit the classification of the document that defines them."""
    g = graph(KG)
    rows = g.query("MATCH (d:Document)-[:RAISED|DEFINES]->(e:Entity) RETURN e.id, d.id").result_set
    docs = {r[0] for r in g.query("MATCH (d:Document) RETURN d.id").result_set}
    return dict(rows), docs


def visible(eid, allowed):
    if allowed is None:
        return True
    parents, docs = _parents()
    if eid in parents:
        return parents[eid] in allowed
    return eid not in docs or eid in allowed


def _knn(g, question, k, allowed, pool=40):
    v = _emb.embed_query(question)
    rows = g.query("CALL db.idx.vector.queryNodes('Chunk', 'embedding', $n, vecf32($v)) YIELD node, score "
                   "RETURN node.id, node.doc, node.text, score ORDER BY score ASC", {"n": pool, "v": v}).result_set
    hits, withheld = [], set()
    for cid, doc, text, score in rows:
        if allowed is not None and doc not in allowed:
            if len(hits) < k:
                withheld.add(doc)
            continue
        if len(hits) < k:
            hits.append({"chunk": cid, "doc": doc, "text": text, "score": round(float(score), 4)})
    return hits, withheld


def vector_context(question, role=None, graph_name=KG, k=6):
    g, allowed = graph(graph_name), allowed_docs(role, graph_name)
    hits, withheld = _knn(g, question, k, allowed)
    ctx = "\n\n".join(h["text"] for h in hits)
    return {"context": ctx, "sources": sorted({h["doc"] for h in hits}), "chunks": hits, "facts": [],
            "withheld": len(withheld), "cypher": "CALL db.idx.vector.queryNodes('Chunk','embedding',k,vecf32($q))"}


def _seed_entities(g, question, hits):
    """Seeds named in the question come first (expanded 2 hops); seeds from retrieved chunks expand 1 hop."""
    q_seeds = set(ID_RE.findall(question))
    ql = question.lower()
    for eid, name in g.query("MATCH (e:Entity) WHERE e.name IS NOT NULL RETURN e.id, e.name").result_set:
        if len(name) > 3 and name.lower() in ql:
            q_seeds.add(eid)
    for eid, title in g.query("MATCH (d:Document) RETURN d.id, d.title").result_set:
        if title and title.lower() in ql:
            q_seeds.add(eid)
    c_seeds = set()
    if hits:
        ids = [h["chunk"] for h in hits[:3]]
        c_seeds = {r[0] for r in g.query("UNWIND $ids AS cid MATCH (c:Chunk {id:cid})-[:MENTIONS]->(e:Entity) RETURN DISTINCT e.id", {"ids": ids}).result_set}
    return sorted(q_seeds), sorted(c_seeds - q_seeds)


HOP2_RELS = "IMPLEMENTS|HAS_CONTROL|SUPERSEDES|APPLIES_TO|DEFINES|MEASURES|RAISED|RAISED_ON|CONCERNS|IMPACTS"
GRAPH_CYPHER = (f"UNWIND $seeds AS sid MATCH (s:Entity {{id:sid}})-[r1:{EXPAND_RELS}]-(m:Entity) "
                f"OPTIONAL MATCH (m)-[r2:{HOP2_RELS}]-(n:Entity) "
                "RETURN s.id, s.name, type(r1), startNode(r1).id = s.id, m.id, m.name, type(r2), "
                "CASE WHEN r2 IS NULL THEN null ELSE startNode(r2).id = m.id END, n.id, n.name LIMIT 3000")
GRAPH_CYPHER_1HOP = (f"UNWIND $seeds AS sid MATCH (s:Entity {{id:sid}})-[r1:{EXPAND_RELS}]-(m:Entity) "
                     "RETURN s.id, s.name, type(r1), startNode(r1).id = s.id, m.id, m.name, null AS r2, null AS f2, null AS n, null AS nn LIMIT 3000")


def graph_context(question, role=None, graph_name=KG, k=4, max_facts=120):
    g, allowed = graph(graph_name), allowed_docs(role, graph_name)
    hits, withheld = _knn(g, question, k, allowed)
    q_seeds, c_seeds = _seed_entities(g, question, hits)
    q_seeds = [s for s in q_seeds if visible(s, allowed)]
    c_seeds = [s for s in c_seeds if visible(s, allowed)]
    rows = []
    if q_seeds:
        rows += g.query(GRAPH_CYPHER, {"seeds": q_seeds}).result_set
    if c_seeds:
        rows += g.query(GRAPH_CYPHER_1HOP, {"seeds": c_seeds}).result_set
    facts, names, hidden = [], {}, set()

    def add(a, rel, b, fwd):
        if not (visible(a, allowed) and visible(b, allowed)):
            hidden.update(x for x in (a, b) if not visible(x, allowed))
            return
        f = f"{a} {rel} {b}" if fwd else f"{b} {rel} {a}"
        if f not in facts:
            facts.append(f)

    for sid, sname, r1, f1, mid, mname, r2, f2, nid, nname in rows:
        names.update({sid: sname, mid: mname})
        add(sid, r1, mid, f1)
    for sid, sname, r1, f1, mid, mname, r2, f2, nid, nname in rows:
        if r2 and nid and nid != sid:
            names[nid] = nname
            add(mid, r2, nid, f2)
    facts = facts[:max_facts]
    seeds = q_seeds + c_seeds
    used = {x for f in facts for x in f.split(" ")[::2]}
    glossary = [f"{i}: {names[i]}" for i in sorted(used) if names.get(i)]
    titles = dict(g.query("MATCH (d:Document) RETURN d.id, d.title").result_set)
    glossary += [f"{i}: {titles[i]}" for i in sorted(used) if i in titles and not names.get(i)]
    ctx = ("GRAPH FACTS (subject RELATION object):\n" + "\n".join(facts) +
           "\n\nENTITY NAMES:\n" + "\n".join(glossary) +
           "\n\nSUPPORTING TEXT:\n" + "\n\n".join(h["text"] for h in hits))
    return {"context": ctx, "sources": sorted({h["doc"] for h in hits} | (used & set(titles))), "chunks": hits,
            "facts": facts, "seeds": seeds, "withheld": len(withheld | {h for h in hidden if h in titles}),
            "cypher": GRAPH_CYPHER}


IMPACT_CYPHER = """MATCH (reg:Entity {id:$reg})<-[:IMPLEMENTS]-(p:Document)
OPTIONAL MATCH (p)-[:HAS_CONTROL]->(c:Entity)
WITH p, collect(DISTINCT c.id) AS ctls
OPTIONAL MATCH (s:Document)-[:IMPLEMENTS]->(p)
OPTIONAL MATCH (s)-[:OWNED_BY]->(dep:Department)
WITH p, ctls, collect(DISTINCT [s.id, dep.name]) AS sops
OPTIONAL MATCH (p)-[:HAS_CONTROL]->(:Entity)<-[:MEASURES]-(k:Entity)
WITH p, ctls, sops, collect(DISTINCT k.id) AS kris
OPTIONAL MATCH (p)-[:HAS_CONTROL]->(:Entity)<-[:RAISED_ON]-(f:Entity)
RETURN p.id, p.title, ctls, sops, kris, collect(DISTINCT f.id)"""


def impact(reg_id, role=None):
    """Scenario 1: everything a regulation touches, in one Cypher query."""
    g, allowed = graph(KG), allowed_docs(role)
    t = time.perf_counter()
    rows = g.query(IMPACT_CYPHER, {"reg": reg_id}).result_set
    ms = (time.perf_counter() - t) * 1000
    out = []
    for pid, title, ctls, sop_depts, kris, findings in rows:
        if not visible(pid, allowed):
            continue
        sops = [(s, d) for s, d in sop_depts if s and visible(s, allowed)]
        out.append({"policy": pid, "title": title, "controls": ctls, "sops": sorted({s for s, _ in sops}),
                    "departments": sorted({d for _, d in sops if d}), "kris": [k for k in kris if visible(k, allowed)],
                    "findings": [f for f in findings if visible(f, allowed)]})
    return {"regulation": reg_id, "policies": out, "ms": round(ms, 1), "cypher": IMPACT_CYPHER}


def entity_ids(text):
    return sorted(set(re.findall(ID_RE, text)))
