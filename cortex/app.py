"""Hugging Face Space entry point (Gradio SDK, ZeroGPU hardware).

Serves the Cortex FastAPI app on port 7860. A minimal Gradio status page is mounted at /gradio,
and one GPU-marked function is registered because ZeroGPU Spaces expect at least one.
"""
import os

import gradio as gr
import uvicorn

try:
    import spaces

    @spaces.GPU(duration=30)
    def gpu_embed(texts):
        """Embeds uploaded-document chunks (registered for ZeroGPU; runs on CPU elsewhere)."""
        from core.embeddings import LocalEmbeddings
        return LocalEmbeddings().embed_documents(texts)
except ImportError:  # local runs without the spaces package
    pass

from app.bootstrap import STATUS
from app.server import app as api

with gr.Blocks(title="Cortex status") as status_ui:
    gr.Markdown("## Cortex status\nThe main app is at [/](/).")
    out = gr.JSON()
    gr.Button("Refresh").click(lambda: STATUS, outputs=out)

app = gr.mount_gradio_app(api, status_ui, path="/gradio")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "7860")))
