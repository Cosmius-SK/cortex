"""Hugging Face Space entry point (Gradio SDK on ZeroGPU hardware).

ZeroGPU expects the Space to be served by Gradio's own launch() and at least one @spaces.GPU function.
So Gradio owns port 7860, and the Cortex FastAPI routes are inserted ahead of Gradio's own routes,
which makes "/" serve the Cortex UI.
"""
import os
import threading

import gradio as gr
import spaces

from app.bootstrap import STATUS, start_background
from app.server import app as api, housekeeping


@spaces.GPU(duration=30)
def gpu_embed(texts):
    """Embeds document chunks; registered for ZeroGPU (runs on CPU outside ZeroGPU)."""
    from core.embeddings import LocalEmbeddings
    return LocalEmbeddings().embed_documents(texts)


with gr.Blocks(title="Cortex status") as demo:
    gr.Markdown("## Cortex status\nThe Cortex app is served at [/](/).")
    out = gr.JSON()
    gr.Button("Refresh").click(lambda: STATUS, outputs=out)

if __name__ == "__main__":
    start_background()
    threading.Thread(target=housekeeping, daemon=True).start()
    # ssr_mode=False: on Spaces, Gradio SSR puts a Node server in front of 7860, which would hide the Cortex routes.
    demo.launch(server_name="0.0.0.0", server_port=int(os.getenv("PORT", "7860")), ssr_mode=False, prevent_thread_lock=True)
    # Cortex routes take priority over Gradio's (the Gradio page itself is not used).
    demo.app.router.routes[0:0] = list(api.router.routes)
    demo.block_thread()
