# Cortex Demo Script

**Link:** https://sk-aiu-cortex.hf.space · **Access PIN:** from the demo owner · **Format:** live walkthrough, with a recording as backup

## Before you start (10 minutes ahead)
1. Open the link. If you see "warming up", wait 1-3 minutes (the Space sleeps when idle).
2. **Settings → Access PIN → Unlock.** The header should show "Shared: 20 of 20 left today".
3. Ask sample question 1 once. The answer is then cached, so it's instant and $0 during the demo.
4. Keep a second tab on **Scenarios** as a fallback if the LLM is busy.

## Executive track (10 minutes)
| Min | Screen | Say | Show |
|---|---|---|---|
| 0-1 | Overview | "Most AI here finds *similar text*. Real questions need *connected facts*. Same 73 PDFs, same model; the only difference is the graph." | Header stats: 1M+ nodes, 0.4 ms query |
| 1-4 | Ask Cortex, question 1 (EU AI Act) | "Left is today's RAG. Right is GraphRAG on FalkorDB." | GraphRAG lists all 6 controls, 4 procedures and 2 open findings. Point at the sources and the tokenomics strip |
| 4-5 | Engineer view → Evaluation | "We measured it on 34 questions with known answers." | **97% vs 70%** recall · **31 vs 19** fully correct · multi-hop **97% vs 47%** · same tokens per correct answer |
| 5-6 | Compare two roles (CRO vs Branch Teller) | "Security is in the graph. The teller never sees audit findings; the model never even receives them." | "N sources withheld" |
| 6-8 | Scenarios → Fraud rings (role: Compliance) | "Same database, beyond RAG: 60 hidden fraud rings in a million records, in under 2 seconds, no false alarms." | Then switch to Branch Teller: access denied |
| 8-9 | Scenarios → Regulatory impact / Risk roll-up | "A new regulation lands: here's everything it touches, instantly. And the bank's risk score, from one control up to the board." | Impact table; bank score 60/100 |
| 9-10 | Close | "Free to run, open to inspect, and you can try it yourself today." | One-pager with the link |

## Engineer track (5 extra minutes)
1. **Engineer view → Pipeline:** LangChain loader and splitter, local embeddings, and pattern extraction (295/295 relationships correct, 0 tokens).
2. **Last queries:** the exact Cypher for vector and GraphRAG retrieval.
3. **Performance panel:** FalkorDB execution times on the 1M-node graph.
4. **Upload:** drop a PDF and ask about it. It goes into a private sandbox graph that's wiped after 24 hours.
5. **Code:** `github.com/Cosmius-SK/AI/tree/main/cortex`. No Docker needed: `python app.py` runs it all locally.

## Likely questions
| Question | Answer |
|---|---|
| "Isn't this rigged for the graph?" | Same PDFs, chunks, embeddings, LLM and prompt. Simple questions tie at 100%, and we show that. |
| "Would Neo4j do the same?" | Out of scope for this demo; a comparison write-up can follow. |
| "Our documents don't have IDs." | Uploads use LLM extraction; try it on the Upload tab. |
| "What does it cost?" | $0 here (free tiers). Tokens per correct answer are about the same as RAG. |
| "Is the data real?" | No. Cortex Bank is 100% synthetic. |
| "Licensing?" | FalkorDB is SSPL; check with Legal before production use. |

## Recording checklist (backup video)
- 1080p browser window, notifications off, PIN already unlocked, questions pre-cached.
- Recorded videos: `docs/video/cortex-exec.mp4` (executive highlights, ~2 min) and `docs/video/cortex-full.mp4` (full tour of every menu, ~3 min).
- Re-record with `python docs/record_demo.py --mode exec|full` after pre-caching the questions.
