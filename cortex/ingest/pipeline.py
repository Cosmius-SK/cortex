"""LangChain ingestion pipeline: PDF -> chunks + embeddings + knowledge graph in FalkorDB.

Usage: python -m ingest.pipeline            (run from cortex/, FalkorDB must be running)

Extraction is hybrid:
  1. Pattern extraction (zero tokens): bank document IDs and section structure give typed
     relationships, e.g. a CTL-* id under "Key Controls" -> (Policy)-[:HAS_CONTROL]->(Control).
  2. LLM extraction (optional, see ingest/llm_extract.py): used for uploads without IDs.
"""
import json
import re
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from content import bank as B
from core.embeddings import DIM, LocalEmbeddings
from core.graph import KG, graph

ROOT = Path(__file__).resolve().parent.parent
PDFS = ROOT / "pdfs"

ID_RE = re.compile(r"\b(REG-[A-Z0-9]+|POL-[A-Z]+-\d{3}|SOP-[A-Z]{3}-\d{3}(?:-V\d)?|CTL-[A-Z]+-\d{2}|SYS-[A-Z]+|"
                   r"RSK-[A-Z]{2}|GRD-\d{3}|KRI-[A-Z]+-\d{2}|AF-\d{4}-\d{3}|AR-\d{4}-\d{2}|RCN-\d{4}-\d{2})\b")
NAME_RE = re.compile(r"([A-Z][A-Za-z0-9&/,' -]{2,80}?) \((" + ID_RE.pattern[2:-2] + r")\)")
KIND = [("REG-", "Regulation"), ("POL-", "Policy"), ("SOP-", "SOP"), ("CTL-", "Control"), ("SYS-", "System"),
        ("RSK-", "Risk"), ("GRD-", "Guardrail"), ("KRI-", "KRI"), ("AF-", "Finding"), ("AR-", "AuditReport"),
        ("RCN-", "ChangeNotice")]
BOILER = re.compile(r"^(CORTEX BANK|Trusted since.*|L\d [A-Z /]+(\s+-\s+Synthetic.*)?|Page \d+|\S+\s+v[\w.]+)$")

# section keyword -> (relation doc->id, id kinds it applies to, reverse?)
SECTION_RULES = [
    ("Regulatory Basis", "IMPLEMENTS", {"Regulation"}, False),
    ("Key Controls", "HAS_CONTROL", {"Control"}, False),
    ("Risks Addressed", "ADDRESSES", {"Risk"}, False),
    ("Implementing Procedures", "IMPLEMENTS", {"SOP"}, True),
    ("Applicable Standards", "APPLIES_TO", {"Guardrail"}, True),
    ("Guardrails", "APPLIES_TO", {"Guardrail"}, True),
    ("Purpose and Scope", "IMPLEMENTS", {"Policy"}, False),
    ("Systems Used", "USES_SYSTEM", {"System"}, False),
    ("Procedure", "HAS_CONTROL", {"Control"}, False),
    ("Version History", "SUPERSEDES", {"SOP"}, False),
    ("STATUS: RETIRED", "SUPERSEDES", {"SOP"}, True),
    ("Applies To", "APPLIES_TO", {"SOP", "Policy", "System"}, False),
    ("Indicators", "DEFINES", {"KRI"}, False),
    ("Findings", "RAISED", {"Finding"}, False),
    ("Change", "CONCERNS", {"Regulation"}, False),
    ("Impacted Policies", "IMPACTS", {"Policy"}, False),
    ("How Cortex Bank Complies", "IMPLEMENTED_BY", {"Policy"}, False),
]
# row subject kind -> (relation, object kinds): e.g. in a KRI table, KRI-x MEASURES the CTL on its row
ROW_RULES = {"Control": ("MITIGATES", {"Risk"}), "KRI": ("MEASURES", {"Control"}), "Finding": ("RAISED_ON", {"Control"})}


LLM_KIND = {k[:3].upper(): k for k in ["Regulation", "Policy", "SOP", "Control", "System", "Risk", "Guardrail", "KRI",
                                        "Finding", "Organisation", "Person", "Concept"]}


def kind(eid):
    if eid.startswith("X-"):  # entities from LLM extraction
        return LLM_KIND.get(eid[2:5], "Concept")
    return next((k for p, k in KIND if eid.startswith(p)), "Concept")


def clean(text):
    return "\n".join(l for l in text.splitlines() if l.strip() and not BOILER.match(l.strip()))


def extract(doc_id, text):
    """Pattern extraction. Returns (entities {id: name}, triples [(s, rel, o)])."""
    names = {m.group(2): m.group(1).strip(" ,") for m in NAME_RE.finditer(text)}
    for m in ID_RE.finditer(text):
        names.setdefault(m.group(1), None)
    triples, rule, subject = set(), None, None
    for line in text.splitlines():
        s = line.strip()
        head = re.match(r"^(\d+\.\s+)?([A-Z][A-Za-z0-9 :&(),-]+)$", s)
        if head:
            title = head.group(2)
            hit = next((r for r in SECTION_RULES if title.startswith(r[0])), None)
            if head.group(1) or title.startswith(("STATUS", "Related Documents", "Approval")):
                rule, subject = hit, None
        for eid in ID_RE.findall(s):
            if eid == doc_id:
                continue
            k = kind(eid)
            if rule and k in rule[2]:
                triples.add((eid, rule[1], doc_id) if rule[3] else (doc_id, rule[1], eid))
                if k in ROW_RULES:
                    subject = eid
            elif subject and k in ROW_RULES[kind(subject)][1]:
                triples.add((subject, ROW_RULES[kind(subject)][0], eid))
            elif rule and rule[0] == "How Cortex Bank Complies":
                pass
    # Regulation summaries: every listed policy implements the summarised regulation.
    regs = [e for e in names if kind(e) == "Regulation"]
    if doc_id.startswith("RS-") and regs:
        triples = {(o, "IMPLEMENTS", regs[0]) if r == "IMPLEMENTED_BY" else (s, r, o) for s, r, o in triples}
    return names, sorted(triples)


def extract_attrs(text):
    """Status attributes from KRI tables and audit findings (e.g. KRI status Breach, finding severity High)."""
    attrs, lines = {}, [l.strip() for l in text.splitlines()]
    for i, l in enumerate(lines):
        m = re.match(r"^(KRI-[A-Z]+-\d{2})$", l)
        if m:
            name = []
            for j in range(i + 1, min(i + 12, len(lines))):
                if re.match(r"^CTL-", lines[j]) and not name[-1:] == ["|"]:
                    name.append("|")
                elif not name or name[-1] != "|":
                    name.append(lines[j])
                if lines[j] in ("Green", "Amber", "Breach"):
                    attrs[m.group(1)] = {"status": lines[j], "current": lines[j - 1], "target": lines[j - 2],
                                         "name": " ".join(x for x in name if x != "|")}
                    break
        m = re.match(r"^(AF-\d{4}-\d{3}): (.+)$", l)
        if m:
            tail = " ".join(lines[i + 1:i + 4])
            sev, due, st = (re.search(p, tail) for p in (r"Severity: (\w+)", r"due:\s*(\d{4}-\d{2}-\d{2})", r"Status: (\w+)"))
            attrs[m.group(1)] = {"name": m.group(2), "severity": sev and sev.group(1), "due": due and due.group(1),
                                 "status": st and st.group(1)}
    return attrs


def load_pdf(path):
    pages = PyPDFLoader(str(path)).load()  # LangChain loader (pypdf)
    return clean("\n".join(p.page_content for p in pages))


SPLITTER = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=120)


def ingest(g, docs, emb, sandbox=False):
    """docs: list of dicts {id, title, type, dept, level, text}. Writes to graph g."""
    for d in docs:
        g.query("MERGE (e:Entity {id:$id}) SET e:Document, e.title=$title, e.type=$type, e.dept=$dept, "
                "e.level=$level, e.version=$version, e.effective=$effective, e.kind='Document'",
                {"version": None, "effective": None, **{k: d.get(k) for k in ("id", "title", "type", "dept", "level", "version", "effective")}})
        names, triples = extract(d["id"], d["text"])
        if d.get("llm"):  # optional LLM extraction (uploads without bank IDs)
            names = {**d["llm"][0], **names}
            triples = sorted(set(triples) | set(d["llm"][1]))
        g.query("UNWIND $rows AS r MERGE (e:Entity {id:r.id}) "
                "SET e.kind = coalesce(e.kind, r.kind), e.name = coalesce(r.name, e.name)",
                {"rows": [{"id": i, "kind": kind(i), "name": n} for i, n in names.items()]})
        attrs = extract_attrs(d["text"])
        if attrs:
            g.query("UNWIND $rows AS r MATCH (e:Entity {id:r.id}) SET e += r.props",
                    {"rows": [{"id": i, "props": a} for i, a in attrs.items()]})
        for rel in {t[1] for t in triples}:
            g.query(f"UNWIND $rows AS r MATCH (a:Entity {{id:r.s}}), (b:Entity {{id:r.o}}) MERGE (a)-[:{rel}]->(b)",
                    {"rows": [{"s": s, "o": o} for s, r, o in triples if r == rel]})
        chunks = SPLITTER.split_text(d["text"])
        header = f"[{d['id']}] {d['title']}\n"
        vecs = emb.embed_documents([header + c for c in chunks])
        g.query("MATCH (doc:Document {id:$doc}) UNWIND $rows AS r "
                "CREATE (doc)-[:HAS_CHUNK]->(c:Chunk {id:r.id, text:r.text, seq:r.seq, doc:$doc, level:$level, "
                "embedding: vecf32(r.v)})",
                {"doc": d["id"], "level": d["level"],
                 "rows": [{"id": f"{d['id']}#{i}", "text": header + c, "seq": i, "v": v} for i, (c, v) in enumerate(zip(chunks, vecs))]})
        keys = [{"id": i, "key": i if i in d["text"] or not n else n} for i, n in {**names, d["id"]: None}.items()]
        g.query("MATCH (c:Chunk {doc:$doc}) UNWIND $keys AS k MATCH (e:Entity {id:k.id}) "
                "WHERE c.text CONTAINS k.key MERGE (c)-[:MENTIONS]->(e)", {"doc": d["id"], "keys": keys})
        print(f"  {d['id']:<16} chunks={len(chunks):<3} entities={len(names):<3} relations={len(triples)}")


def init_schema(name):
    g = graph(name)
    try:
        g.delete()
    except Exception:
        pass
    g = graph(name)
    for label, prop in [("Entity", "id"), ("Chunk", "doc"), ("Role", "id"), ("Department", "code")]:
        g.query(f"CREATE INDEX FOR (n:{label}) ON (n.{prop})")
    g.query(f"CREATE VECTOR INDEX FOR (c:Chunk) ON (c.embedding) OPTIONS {{dimension:{DIM}, similarityFunction:'cosine'}}")
    return g


def build_kg():
    g = init_schema(KG)

    manifest = json.loads((PDFS / "manifest.json").read_text())
    docs = [{**m, "text": load_pdf(PDFS / m["file"])} for m in manifest]
    ingest(g, docs, LocalEmbeddings())

    # Organisation layer: departments, roles and graph-native access control.
    g.query("UNWIND $rows AS r CREATE (:Department {code:r[0], name:r[1], head:r[2]})", {"rows": [list(d[:3]) for d in B.DEPARTMENTS]})
    g.query("MATCH (d:Document) MATCH (dep:Department) WHERE dep.code = d.dept CREATE (d)-[:OWNED_BY]->(dep)")
    g.query("UNWIND $rows AS r CREATE (:Role {id:r[0], name:r[1], clearance:r[2]})", {"rows": [list(r[:3]) for r in B.ROLES]})
    access = [{"r": r[0], "d": m["id"]} for r in B.ROLES for m in manifest if B.can_access(r[0], m["level"], m["dept"])]
    g.query("UNWIND $rows AS x MATCH (r:Role {id:x.r}), (d:Document {id:x.d}) CREATE (r)-[:CAN_ACCESS]->(d)", {"rows": access})
    stats = g.query("MATCH (n) RETURN count(n)").result_set[0][0], g.query("MATCH ()-[e]->() RETURN count(e)").result_set[0][0]
    print(f"Knowledge graph: {stats[0]:,} nodes, {stats[1]:,} relationships, {len(manifest)} documents")


if __name__ == "__main__":
    build_kg()
