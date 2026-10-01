# Cortex: why FalkorDB for AI engagements, and more

A GraphRAG demo on a 100% synthetic, 100-year-old bank ("Cortex Bank", est. 1926), built on **FalkorDB + LangChain**.
It answers the same questions two ways, plain vector RAG and GraphRAG, and measures the difference.

- **Live demo:** https://sk-aiu-cortex.hf.space (an Access PIN from the owner unlocks new questions)
- **Code:** [`cortex/`](cortex/) · run locally with `python app.py`
- **Design and decisions:** [`cortex/docs/DESIGN.md`](cortex/docs/DESIGN.md) · [`cortex/docs/DECISIONS.md`](cortex/docs/DECISIONS.md)
- **Deploy:** [`.github/workflows/deploy-cortex-space.yml`](.github/workflows/deploy-cortex-space.yml) pushes `cortex/` to the Hugging Face Space on every change to `main`

All data is synthetic. Shared for evaluation; all rights reserved unless a licence file says otherwise.
