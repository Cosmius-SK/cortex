"""Schema-guided LLM extraction for uploaded PDFs that don't carry bank IDs (LangChain structured output)."""
import re
from typing import List

from pydantic import BaseModel, Field

KINDS = ["Regulation", "Policy", "SOP", "Control", "System", "Risk", "Guardrail", "KRI", "Finding", "Organisation", "Person", "Concept"]
RELS = ["IMPLEMENTS", "HAS_CONTROL", "MITIGATES", "USES_SYSTEM", "SUPERSEDES", "APPLIES_TO", "MEASURES", "RAISED_ON",
        "CONCERNS", "IMPACTS", "OWNS", "RELATED_TO"]


class Ent(BaseModel):
    name: str = Field(description="Canonical entity name as written in the text")
    kind: str = Field(description=f"One of: {', '.join(KINDS)}")


class Rel(BaseModel):
    source: str = Field(description="Source entity name")
    relation: str = Field(description=f"One of: {', '.join(RELS)}")
    target: str = Field(description="Target entity name")


class Extraction(BaseModel):
    entities: List[Ent]
    relations: List[Rel]


PROMPT = ("Extract the key entities and relationships from this document excerpt for a bank knowledge graph. "
          "Use only the allowed kinds and relations. Keep 5-25 entities. Do not invent facts.\n\n{text}")


def slug(name, kind):
    return f"X-{kind[:3].upper()}-" + re.sub(r"[^A-Z0-9]+", "-", name.upper()).strip("-")[:40]


def llm_extract(llm, text, max_chars=12000):
    """Returns ({id: name}, [(s, rel, o)]) plus token usage."""
    structured = llm.with_structured_output(Extraction, include_raw=True)
    out = structured.invoke(PROMPT.format(text=text[:max_chars]))
    parsed, raw = out["parsed"], out["raw"]
    usage = getattr(raw, "usage_metadata", None) or {}
    if not parsed:
        return {}, [], usage
    ids = {e.name.lower(): slug(e.name, e.kind if e.kind in KINDS else "Concept") for e in parsed.entities}
    names = {ids[e.name.lower()]: e.name for e in parsed.entities}
    triples = [(ids[r.source.lower()], r.relation if r.relation in RELS else "RELATED_TO", ids[r.target.lower()])
               for r in parsed.relations if r.source.lower() in ids and r.target.lower() in ids]
    return names, triples, usage
