"""Vector RAG vs GraphRAG on 34 questions with known answers (derived from content/bank.py).

Usage: GOOGLE_API_KEY=... python -m eval.run_eval [--provider gemini|claude] [--role ROLE-CRO]
Score = share of the expected IDs that appear in the answer (recall), plus tokens and latency.
Writes eval/results.json.
"""
import argparse
import json
import time
from pathlib import Path

from content import bank as B
from core.llm import answer
from core.retrieval import entity_ids

OUT = Path(__file__).resolve().parent / "results.json"
REG = {r[0]: r[1] for r in B.REGULATIONS}


def questions():
    qs = []
    for rid, short, *_ in B.REGULATIONS:
        pols = [p[0] for p in B.POLICIES if rid in p[3]]
        qs.append(("aggregation", f"Which policies implement {short}?", pols))
        sops = sorted({s[0] for s in B.SOPS if set(s[3]) & set(pols)})
        if sops:
            qs.append(("multi-hop", f"Which procedures are affected by {short} through the policies that implement it?", sops))
    for aid, *_, findings in B.AUDIT_REPORTS:
        for f in findings:
            sops = sorted({s[0] for s in B.SOPS for _, cs in s[5] for c in cs if c == f[3]})
            qs.append(("multi-hop", f"Which control does audit finding {f[0]} relate to, and which procedures use that control?", [f[3]] + sops))
    breach = [(i[0], i[2]) for k in B.KRI_FRAMEWORKS for i in k[4] if i[5] == "Breach"]
    qs.append(("cross-document", "Which KRIs are in breach and which controls do they measure?",
               [k for k, _ in breach] + sorted({c for _, cs in breach for c in cs})))
    for l in B.LEGACY_SOPS:
        qs.append(("single-fact", f"Which procedure replaced the retired '{l[1]}'?", [l[6]]))
    return qs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="gemini")
    ap.add_argument("--role", default="ROLE-CRO")
    ap.add_argument("--sleep", type=float, default=4.0, help="pause between calls (free-tier rate limits)")
    a = ap.parse_args()
    rows = []
    for qtype, q, gold in questions():
        for mode in ("vector", "graph"):
            r = answer(q, mode, a.role, a.provider)
            got = set(entity_ids(r.get("answer") or ""))
            t = r.get("tokenomics", {})
            rows.append({"type": qtype, "question": q, "mode": mode, "expected": gold,
                         "recall": round(len(got & set(gold)) / len(gold), 3), "input_tokens": t.get("input_tokens"),
                         "output_tokens": t.get("output_tokens"), "cost_usd": t.get("cost_usd"),
                         "llm_ms": r.get("llm_ms"), "retrieval_ms": r.get("retrieval_ms")})
            print(f"{mode:<6} {rows[-1]['recall']:.2f}  {q[:90]}")
            time.sleep(a.sleep)
    summary = {}
    for mode in ("vector", "graph"):
        rs = [r for r in rows if r["mode"] == mode]
        summary[mode] = {"avg_recall": round(sum(r["recall"] for r in rs) / len(rs), 3),
                         "fully_correct": sum(r["recall"] == 1 for r in rs), "questions": len(rs),
                         "input_tokens": sum(r["input_tokens"] or 0 for r in rs),
                         "output_tokens": sum(r["output_tokens"] or 0 for r in rs),
                         "by_type": {t: round(sum(r["recall"] for r in rs if r["type"] == t) /
                                              max(1, sum(r["type"] == t for r in rs)), 3) for t in {r["type"] for r in rs}}}
        s = summary[mode]
        s["tokens_per_fully_correct_answer"] = round((s["input_tokens"] + s["output_tokens"]) / max(1, s["fully_correct"]))
    OUT.write_text(json.dumps({"provider": a.provider, "role": a.role, "summary": summary, "rows": rows}, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
