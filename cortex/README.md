---
title: Cortex
emoji: 🧠
colorFrom: blue
colorTo: yellow
sdk: gradio
sdk_version: 6.29.0
python_version: "3.12"
app_file: app.py
pinned: false
license: mit
short_description: Why FalkorDB for AI engagements, and more
---

# Cortex: Why FalkorDB for AI engagements, and more

GraphRAG demo on **Cortex Bank**, a synthetic 100-year-old bank. 73 bank PDFs are ingested with LangChain into
FalkorDB. The same questions are answered by plain vector RAG and by GraphRAG, with role-based access control,
tokenomics, one-click scenarios (regulatory impact, fraud rings, risk roll-up, lineage, performance) and private
upload sandboxes. All data is synthetic.

- Design: [`docs/DESIGN.md`](docs/DESIGN.md)
- Live demo: https://huggingface.co/spaces/sk-aiu/cortex (deployed from GitHub `Cosmius-SK/AI`, folder `cortex/`)

## Run locally

```bash
cd cortex
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt gradio==6.29.0
python app.py            # starts embedded FalkorDB, builds both graphs, serves http://localhost:7860
```

Optional environment variables:

| Variable | Purpose |
|---|---|
| `GOOGLE_API_KEY` | Shared Gemini key (free tier) for the demo |
| `CORTEX_ACCESS_PIN` | PIN testers enter to use the shared key |
| `CORTEX_GEMINI_MODEL` | Gemini model name (default: newest Flash model available to the key, discovered automatically) |
| `CORTEX_OPS_SCALE` | Operational graph size (1.0 = ~1M nodes; auto-sized from RAM when unset) |
| `FALKOR_HOST` / `FALKOR_PORT` | Use an existing FalkorDB server instead of the embedded one |

## Layout

| Path | What |
|---|---|
| `content/bank.py` | The bank's knowledge base (single source of truth and answer key) |
| `generator/` | PDF renderer and operational data generator (seeded, with fraud rings) |
| `pdfs/` | The 73 generated PDFs |
| `ingest/` | LangChain pipeline: PDFs to chunks, embeddings and graph (pattern + LLM extraction) |
| `core/` | Retrieval (vector RAG vs GraphRAG, role filter), LLM gateway with tokenomics, scenarios |
| `app/` | FastAPI server, limits, PINs, uploads, static UI |
| `eval/` | Extraction accuracy check and question set |
