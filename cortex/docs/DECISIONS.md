# Cortex: Decision Log

Why Cortex is the way it is. Each entry: **decision · options considered · why · lesson.** Source for the Learning Portal (DESIGN.md §16).

## Purpose and audience
| # | Decision | Options considered | Why | Lesson |
|---|---|---|---|---|
| 1 | Prove FalkorDB is the best graph engine for an AI- and RAG-heavy environment | An AI-news product; a Neo4j migration study | The "AI news" idea was only a vehicle; the real question was "why a graph engine for AI" | Name the real goal early; the use case is just the stage |
| 2 | Audience: executives and engineers, testing it themselves | Live demos only | Testers must use it without the owner or a laptop running | Self-serve demos scale; design for "no presenter in the room" |
| 3 | Synthetic 100-year-old bank, "Cortex Bank" (est. 1926), 12 departments | Real or anonymised documents | Zero data risk; a known answer key makes results measurable | Synthetic data with an answer key turns a demo into evidence |
| 4 | Drop the Neo4j comparison; position FalkorDB as greenfield | Head-to-head benchmark | A colleague noted there was no Neo4j AI work to compare against | Fight the battle that exists, not the one you planned |
| 5 | Wording: "Why FalkorDB for AI engagements, and more" | "Why start AI on FalkorDB" | Broader; covers RAG plus fraud, impact and roll-ups | Positioning words shape the whole demo |

## Content and ingestion
| # | Decision | Options considered | Why | Lesson |
|---|---|---|---|---|
| 6 | Hybrid ingestion: 73 generated PDFs plus a 1M-node operational graph | PDFs only; structured data only | PDFs show RAG vs GraphRAG; the big graph shows scale and "beyond RAG" | Show both the AI use case and the scale story |
| 7 | Claude generates all content (policies, SOPs, KRIs, audits, guardrails) | Hand-written or public documents | Speed, consistency, and a built-in answer key | Generated content is fine when it's labelled synthetic |
| 8 | Bank IDs extracted by patterns (0 tokens, 295/295 correct); LLM extraction only for uploads | LLM extraction for everything | Free, exact and repeatable on known formats; the LLM handles unknown formats | Use the cheapest reliable tool; save the LLM for ambiguity |
| 9 | Local embeddings (bge-base, 768-d) | Paid embedding APIs | $0, private, fast enough on CPU | Embeddings don't have to cost money |

## AI and retrieval
| # | Decision | Options considered | Why | Lesson |
|---|---|---|---|---|
| 10 | LangChain for loaders, splitters and chat models | Hand-rolled code | Standard, recognisable to engineers, easy model swaps | Use the lingua franca your audience knows |
| 11 | Gemini free tier by default; bring-your-own Gemini or Claude key | Paid Claude only | $0 for testers; heavy users bring their own key | Free default + BYOK = no budget needed |
| 12 | Discover Gemini models automatically and fall back on 503/429 | A hard-coded model | gemini-2.5-flash was retired mid-build; demand spikes return 503 | Never hard-code a free-tier model name |
| 13 | Role-aware GraphRAG: (Role)-[:CAN_ACCESS]->(Document) filtered before the LLM | Filter after the answer | Restricted text never reaches the model | Security belongs in retrieval, not in the prompt |
| 14 | Same PDFs, chunks, embeddings, LLM and prompt for both approaches | Tuning each separately | A fair test is the only credible one | Make the comparison impossible to call rigged |
| 15 | 34-question evaluation with known answers (run 2: 97% vs 70% recall, 31 vs 19 fully correct, multi-hop 97% vs 47%, same tokens per correct answer) | Anecdotes | Numbers persuade executives; ties on simple questions build trust | Show where you don't win, too (cross-document 40% each) |
| 16 | Tokenomics on every answer | Hide costs | Cost per correct answer is the executive metric | Measure value per token, not tokens alone |

## FalkorDB specifics
| # | Decision | Options considered | Why | Lesson |
|---|---|---|---|---|
| 17 | Embedded FalkorDB (Redis module binaries) inside the app container | Docker; managed cloud | Hugging Face's Docker option was paid; embedded is free and has no network hop | Embeddable engines unlock free hosting |
| 18 | Graph + vector in one engine; separate graphs for KG, ops and each sandbox | Separate vector DB | No sync; a sandbox wipe is one GRAPH.DELETE | One engine, many graphs = simple multi-tenancy |
| 19 | Staged WITH clauses for multi-collect queries | A single query with two collect(DISTINCT) | Hit an engine bug that returned wrong results | Verify aggregate queries against known answers |
| 20 | Wait for indexes before measuring; performance runs fresh | Measure at startup | First numbers were 196 ms vs 0.17 ms after indexing | Benchmarks lie if indexes are still building |

## Hosting, security and limits
| # | Decision | Options considered | Why | Lesson |
|---|---|---|---|---|
| 21 | Free Hugging Face Space (Gradio SDK, ZeroGPU), deployed from GitHub Actions | Laptop + tunnel; AWS | Always on without the owner's laptop; AWS has cost and no account yet | AWS is future state; free tiers first |
| 22 | Access PIN for the shared key (8 h session, lockout after 5 failures); BYOK encrypted in the browser | Open access | Protects the free quota; keys never stored on the server | Protect shared keys; never hold other people's keys |
| 23 | Limits called out everywhere: 24 h sandbox wipe, 4 h idle reset, quotas, upload caps | Silent limits | Testers trust what's visible; "nothing is limited silently" | Publish your limits; it builds trust |
| 24 | Answer cache that bypasses the PIN for repeat questions | Always call the LLM | Instant, $0 demos; reliable when the free tier is busy | Cache the demo path |
| 25 | Refund the quota when no answer is generated | Always charge | Fairness to testers | Small fairness rules matter |

## Presentation
| # | Decision | Options considered | Why | Lesson |
|---|---|---|---|---|
| 26 | Infographic one-pager, not a text one-pager | Text brief | Executives skim; visuals carry the numbers | Match the format to how people consume |
| 27 | Two captioned videos (executive ~2 min, full tour ~3 min) | One long video | Different audiences, different depth | One video per audience |
| 28 | X-Ray tab: live engine internals, real EXPLAIN/PROFILE plans, life of a question | Static architecture slide | Engineers trust what they can inspect live | Show the machine running, not a diagram of it |
| 29 | 94 s narrated 3D film, code-rendered; open TTS (Kokoro, Apache-2.0) and a synthesised score | Studio video; MusicGen (non-commercial licence) | $0, re-renderable in 15 min, licence-clean | Check model licences before "commercial" use |

## Parked (future)
Neo4j comparison write-up · AWS deployment · live AI-news / regulatory feed as `Signal` nodes · FalkorDB licence (SSPL) review with Legal before production.
