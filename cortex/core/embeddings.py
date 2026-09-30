"""Local CPU embeddings (no API cost) exposed through LangChain's Embeddings interface."""
import os
from functools import lru_cache

from langchain_core.embeddings import Embeddings

MODEL = "BAAI/bge-base-en-v1.5"
DIM = 768


@lru_cache(maxsize=1)
def _model():
    from fastembed import TextEmbedding
    path = os.getenv("CORTEX_EMBED_PATH")  # pre-downloaded model dir (offline builds)
    return TextEmbedding(MODEL, specific_model_path=path) if path else TextEmbedding(MODEL)


class LocalEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [v.tolist() for v in _model().embed(texts, batch_size=32)]

    def embed_query(self, text):
        return next(iter(_model().query_embed(text))).tolist()
