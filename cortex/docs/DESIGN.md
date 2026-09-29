# Cortex — FalkorDB vs Neo4j Demo (Design v0.1)

> Status: **DRAFT for review** · 2026-09-29 · Working name "Cortex" (final name TBD)

## 1. Goal
Prove, with reproducible evidence, that **FalkorDB** is a better fit than our incumbent **Neo4j** for
graph + GraphRAG workloads in an enterprise full of RAG solutions.

- **Vehicle:** "Cortex Bank" — a synthetic 100-year-old bank (est. 1926) with departments, SOPs,
  policies, guardrails, scoring metrics, and operational data.
- **Audience:** Executives (story, impact, ROI) **and** Engineers (benchmarks, reproducibility).
- **Access:** Self-serve, public URL, always available — no presenter or laptop needed.
- **Format:** Hybrid — live walkthrough + recorded backup video.
- **Deadline:** 2 days.

## 2. Principles
1. **Measure, don't claim.** Every advantage shown is a measured result on identical hardware and data.
2. **Fair fight.** Same host, same data, equivalent indexes, warm caches, versions and configs published.
3. **Honest about trade-offs.** Where Neo4j wins or ties, we show it. Credibility > cheerleading.
4. **Reproducible.** Engineers can `docker compose up` and re-run every number.

## 3. Architecture

```
            Hugging Face Docker Space (free, 16 GB RAM, 2 vCPU, port 7860)
 ┌──────────────────────────────────────────────────────────────────────┐
 │ supervisord                                                          │
 │  ├─ FalkorDB (redis-server + falkordb module)      :6379  ~4 GB     │
 │  ├─ Neo4j 5.26 LTS Community (heap 3G, pagecache 3G) :7687 ~6.5 GB  │
 │  └─ App: FastAPI + static web UI                   :7860  ~2 GB     │
 │        ├─ Loader (bundled CSV → both DBs at startup)                │
 │        ├─ Benchmark runner (same Cypher on both)                     │
 │        ├─ GraphRAG service → Claude Sonnet 5.5 (API)                │
 │        └─ Local embeddings (small open-source model, CPU)           │
 └──────────────────────────────────────────────────────────────────────┘
```

- **Single container** so both databases share identical hardware (fair benchmark).
- **Ephemeral disk:** data ships inside the image as compressed CSV, loaded on boot.
  Load times for both DBs are captured and shown as a benchmark metric.
- **Sleep/wake:** the Space sleeps after ~48h idle; a visit wakes it (~1–3 min incl. load).
  The landing page shows a "warming up" status while loading.
- **Local parity:** the same image runs via `docker compose up` for engineers.

## 4. Graph Model

### 4.1 Knowledge layer (the "organisational brain")
| Node | Examples / key props |
|---|---|
| `Department` | Retail, Corporate & Commercial, Wealth, Treasury & Markets, Credit, Risk, Compliance (AML/KYC), Operations, IT & Cyber, HR, Legal, Internal Audit |
| `Role`, `Person` | Title, grade, clearance level |
| `SOP`, `SOPStep` | Versioned; `effective_from/to`; text + embedding |
| `Policy`, `Control` | Owner, review cycle, text + embedding |
| `Risk` | Category (credit/market/op/conduct/cyber), inherent/residual score |
| `Regulation` | Basel III/IV, AML/KYC, GDPR, DORA, PCI-DSS, SOX, BCBS 239, EU AI Act |
| `Guardrail` | Segregation of duties, maker-checker, AI-usage limits, data-access rules |
| `KPI`, `KRI`, `Score` | Targets, thresholds, current values |
| `System` | Core banking (legacy mainframe), CRM, payments, data lake |
| `AuditFinding`, `Incident` | Severity, status, dates |
| `Entity` (history) | Acquired banks (M&A over 100 years), legacy branches |
| `Signal` | External news / regulatory updates (the original "AI news" idea) |

Key relationships:
`(Department)-[:OWNS]->(SOP|Policy)` · `(SOP)-[:SUPERSEDES]->(SOP)` · `(SOP)-[:HAS_STEP]->(SOPStep)`
`(Policy)-[:IMPLEMENTS]->(Regulation)` · `(Control)-[:MITIGATES]->(Risk)` · `(SOPStep)-[:ENFORCES]->(Control)`
`(Guardrail)-[:APPLIES_TO]->(Role|System|SOP)` · `(Role)-[:CAN_ACCESS]->(Policy|System)`
`(KPI|KRI)-[:MEASURES]->(Control|Department)` · `(Signal)-[:AFFECTS]->(Regulation|System)`
`(AuditFinding)-[:RAISED_ON]->(Control)` · `(Entity)-[:MERGED_INTO]->(Entity)`

### 4.2 Operational layer (scale + fraud)
`Customer`, `Account`, `Transaction`, `Device`, `IP`, `Address`, `Branch`, `Merchant` with injected
**fraud rings** (shared devices/addresses, circular money flows, mule chains).

### 4.3 Scale tiers
| Tier | Nodes | Rels | Where |
|---|---|---|---|
| S | ~50k | ~200k | Unit tests, CI |
| **M (default)** | **~1M** | **~5M** | **HF Space (16 GB)** |
| L | ~10M | ~50M | Local/bigger VM (engineers, optional) |

Generator is deterministic (fixed seed) — same data on every boot and every machine.

## 5. Synthetic Data Generation
- **Knowledge content** (SOPs, policies, guardrails, KPIs, history narratives, signals):
  authored once during the build and committed as JSON/Markdown — **no API cost at runtime**.
- **Operational data:** Python generator (Faker + seeded randomness), fraud patterns injected with
  ground-truth labels (so detection accuracy is measurable).
- **Embeddings:** computed at build time with a small local CPU model; bundled with the data.

## 6. Demo Scenarios (each shows *why graph*)
| # | Scenario | What it proves |
|---|---|---|
| 1 | **Regulatory impact:** "EU AI Act amendment lands — what's affected?" → Regulation → Policies → Controls → SOPs → Teams → KPIs | Multi-hop traversal (4–6 hops) in ms; vector-only RAG can't do this |
| 2 | **Guardrail-aware assistant:** answers respect the asker's role/clearance via graph access paths | Graph-native access control for AI |
| 3 | **Fraud ring detection:** find rings via shared devices/circular flows | Classic graph strength at scale |
| 4 | **Scoring roll-up:** control effectiveness → department KRI → bank-wide risk score | Aggregation over hierarchies |
| 5 | **Explainable answers:** every LLM answer shows the graph path used as evidence | Trust / auditability |
| 6 | **Change log & versioning:** a Signal updates → linked policy flagged → full audit trail | Temporal/lineage modelling |
| 7 | **Multi-tenant:** one graph per department in a single FalkorDB instance | Isolation without Enterprise licensing |

## 7. Benchmark Methodology
- **Same Cypher** on both (openCypher subset), with a small dialect shim where syntax differs
  (differences are logged and shown — useful migration evidence).
- **Query suite:** point lookups, 2/4/6-hop traversals, shortest path, aggregations,
  vector-KNN, hybrid vector+traversal, fraud ring pattern, concurrent read load, bulk load, writes.
- **Metrics:** p50/p95/p99 latency, throughput (QPS), load time, RAM used, container footprint.
- **Protocol:** warm-up runs discarded, N=50 runs per query, sequential + concurrent (1/8/32 clients).
- **Published:** versions, configs, hardware, raw results (CSV) — downloadable from the UI.
- **Hypotheses to test (not assumed):**
  - FalkorDB lower latency on multi-hop traversals (sparse-matrix / GraphBLAS engine)
  - FalkorDB lower memory footprint for the same graph
  - Multi-graph isolation in one instance (Neo4j Community = single database; multi-DB is Enterprise)
  - Hybrid vector + graph in one query on both — compare latency & ergonomics
  - Neo4j likely ahead on: tooling (Bloom, GDS algorithms), ecosystem maturity — stated openly

## 8. GraphRAG vs Vector RAG Evaluation
- ~30 questions with gold answers across 3 types: single-fact, multi-hop, aggregation/compliance.
- Pipelines compared: **(a) vector-only RAG**, **(b) GraphRAG on Neo4j**, **(c) GraphRAG on FalkorDB**.
- Metrics: answer accuracy (graded vs gold), retrieval latency, end-to-end latency, token cost.
- LLM: **Claude Sonnet 5.5**. Text-to-Cypher is **read-only** (write clauses rejected, query timeout).

## 9. UI
- **Executive view:** landing KPIs, 7 one-click scenarios, graph visualisation, head-to-head
  latency bars, "Ask Cortex" chat with evidence paths.
- **Engineer view:** benchmark console (pick query → run on both → live results), raw Cypher,
  configs, CSV download, link to repo.
- Stack: FastAPI backend + lightweight static front end (graph viz via Cytoscape.js from CDN).

## 10. Cost & Abuse Controls (public URL)
- `ANTHROPIC_API_KEY` stored as an HF Space secret — never sent to the browser.
- Shared **passcode** gate for the chat; per-session daily question limit; request size limits.
- **Pre-computed answers** for scripted scenarios (zero cost, works if the API is down).
- Owner sets a **spend limit** in the Anthropic Console (suggested $25).
- Expected spend: ~$0.03 per question → ~$6 per 200 questions.

## 11. Repository Layout
```
cortex/
  docs/DESIGN.md, BENCHMARK.md, DEMO_SCRIPT.md
  data/knowledge/        # authored SOPs, policies, guardrails… (JSON/MD)
  generator/             # operational data + fraud injection (seeded)
  loader/                # CSV → FalkorDB & Neo4j
  bench/                 # query suite, runner, results
  app/                   # FastAPI + static UI + GraphRAG
  deploy/                # Dockerfile (HF Space), supervisord.conf, docker-compose.yml
  tests/
```

## 12. Two-Day Plan
| When | Deliverable |
|---|---|
| Day 1 AM | Schema, knowledge content, generator (tier S/M), loader for both DBs |
| Day 1 PM | Benchmark suite + runner; first results; container builds locally |
| Day 2 AM | App: exec + engineer views, scenarios, GraphRAG with guardrails |
| Day 2 PM | HF Space deploy, demo script, recorded backup video, README |

## 13. Risks & Open Items
| Risk | Mitigation |
|---|---|
| 16 GB shared by 2 DBs + app | Tier M sizing; memory limits per process; tier L only locally |
| Space cold start (sleep) | Warm-up page; compressed bulk load; optional keep-alive ping |
| Cypher dialect gaps | Shim + documented list (doubles as migration evidence) |
| Benchmark seen as biased | Open configs, raw data, reproducible locally, Neo4j wins shown |
| Licensing (FalkorDB SSPL, Neo4j Community GPL/Enterprise commercial) | Flag to Legal before production use |
| Neo4j version | Using 5.26 LTS (n-1); swap image tag once confirmed |

**Open:** final project name · Neo4j edition confirmation · who owns the Anthropic key / HF Space.
