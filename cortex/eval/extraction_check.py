"""Compare relationships extracted from the PDFs with the answer key in content/bank.py.

Usage: python -m eval.extraction_check   (run from cortex/)
"""
from content import bank as B
from core.graph import KG, graph


def gold():
    t = set()
    for pid, _, _, regs, ctls, *_ in B.POLICIES:
        t |= {(pid, "IMPLEMENTS", r) for r in regs} | {(pid, "HAS_CONTROL", c) for c in ctls}
    for c in B.CONTROLS:
        t |= {(c[0], "MITIGATES", r) for r in c[5]}
    for sid, _, _, pols, systems, steps, *_ in B.SOPS:
        t |= {(sid, "IMPLEMENTS", p) for p in pols} | {(sid, "USES_SYSTEM", s) for s in systems}
        t |= {(sid, "HAS_CONTROL", c) for _, cs in steps for c in cs}
    t |= {(l[6], "SUPERSEDES", l[0]) for l in B.LEGACY_SOPS}
    for gid, _, _, applies, *_ in B.GUARDRAILS:
        t |= {(gid, "APPLIES_TO", a) for a in applies if a[:3] in ("SOP", "POL", "SYS")}
    for kid, _, _, _, inds in B.KRI_FRAMEWORKS:
        for i in inds:
            t |= {(kid, "DEFINES", i[0])} | {(i[0], "MEASURES", c) for c in i[2]}
    for aid, *_, findings in B.AUDIT_REPORTS:
        for f in findings:
            t |= {(aid, "RAISED", f[0]), (f[0], "RAISED_ON", f[3])}
    for cid, _, _, rid, _, pols, _ in B.CHANGE_NOTICES:
        t |= {(cid, "CONCERNS", rid)} | {(cid, "IMPACTS", p) for p in pols}
    return t


def main():
    g = graph(KG)
    rels = {"IMPLEMENTS", "HAS_CONTROL", "MITIGATES", "USES_SYSTEM", "SUPERSEDES", "APPLIES_TO", "DEFINES", "MEASURES",
            "RAISED", "RAISED_ON", "CONCERNS", "IMPACTS"}
    rows = g.query("MATCH (a:Entity)-[r]->(b:Entity) RETURN a.id, type(r), b.id").result_set
    got = {tuple(r) for r in rows if r[1] in rels}
    ref = gold()
    tp = got & ref
    print(f"gold={len(ref)} extracted={len(got)} correct={len(tp)} "
          f"precision={len(tp) / max(1, len(got)):.1%} recall={len(tp) / max(1, len(ref)):.1%}")
    for label, items in (("missed", ref - got), ("extra", got - ref)):
        for x in sorted(items)[:15]:
            print(f"  {label}: {x}")


if __name__ == "__main__":
    main()
