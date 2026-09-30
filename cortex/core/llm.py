"""LLM gateway (LangChain) + answer generation with tokenomics.

Providers:
  gemini : Google Gemini, free tier by default (owner key GOOGLE_API_KEY, or the tester's own key)
  claude : Claude Sonnet 5.5 (tester's own key)
"""
import os
import time

from core.retrieval import entity_ids, graph_context, vector_context

GEMINI_MODEL = os.getenv("CORTEX_GEMINI_MODEL")  # unset: pick the newest available Flash model automatically
_GEMINI_PICK = {}
CLAUDE_MODEL = "claude-sonnet-5-5"
# USD per 1M tokens (input, output). Gemini free tier costs $0; set CORTEX_GEMINI_PRICE="in,out" to show a paid equivalent.
PRICES = {"claude": (2.00, 10.00),
          "gemini": tuple(float(x) for x in os.getenv("CORTEX_GEMINI_PRICE", "0,0").split(","))}

SYSTEM = ("You are Cortex, the knowledge assistant of Cortex Bank. Answer ONLY from the context provided. "
          "Cite document and entity IDs in square brackets, e.g. [POL-AI-001]. When asked for lists, be complete. "
          "If the context does not contain the answer, say so plainly. Be concise.")


def gemini_models(api_key):
    """Flash models this key can use, best first: newest standard Flash, then newest Flash-Lite, then Google's alias.
    Model names change over time, so they are discovered rather than hard-coded."""
    if GEMINI_MODEL:
        return [GEMINI_MODEL]
    if api_key not in _GEMINI_PICK:
        import re
        from google import genai
        client = genai.Client(api_key=api_key)  # keep a reference: the pager needs the client alive while iterating
        try:
            models = list(client.models.list())
        except Exception:
            models = []  # listing not permitted: fall back to Google's rolling alias
        std, lite = [], []
        for m in models:
            name = (m.name or "").removeprefix("models/")
            if "generateContent" not in (m.supported_actions or []) or "flash" not in name:
                continue
            if re.search(r"image|tts|audio|live|thinking|exp|preview|embed|8b", name):
                continue
            (lite if "lite" in name else std).append(name)
        ver = lambda n: [int(x) for x in re.findall(r"\d+", n)]
        _GEMINI_PICK[api_key] = sorted(std, key=ver, reverse=True)[:2] + sorted(lite, key=ver, reverse=True)[:1] + ["gemini-flash-latest"]
    return _GEMINI_PICK[api_key]


def chat_model(provider, api_key, model=None):
    if provider == "claude":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=CLAUDE_MODEL, api_key=api_key, max_tokens=2048, timeout=60)
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model=model or gemini_models(api_key)[0], google_api_key=api_key, temperature=0,
                                  timeout=60, max_retries=1)


BUSY = ("503", "UNAVAILABLE", "overloaded", "high demand", "429", "RESOURCE_EXHAUSTED")


def invoke_with_fallback(provider, api_key, messages):
    """Gemini's free tier is sometimes overloaded (503) or rate-limited (429): try the next model instead of failing."""
    candidates = gemini_models(api_key) if provider == "gemini" else [CLAUDE_MODEL]
    last = None
    for i, model in enumerate(dict.fromkeys(candidates)):
        llm = chat_model(provider, api_key, model)
        try:
            return llm.invoke(messages), model, i
        except Exception as e:
            last = e
            if not any(b in str(e) for b in BUSY):
                raise
            time.sleep(1.5)
    raise last


def answer(question, mode="graph", role=None, provider="gemini", api_key=None, graph_name="cortex_kg"):
    t0 = time.perf_counter()
    ctx = graph_context(question, role, graph_name) if mode == "graph" else vector_context(question, role, graph_name)
    t_retrieval = (time.perf_counter() - t0) * 1000
    key = api_key or (os.getenv("GOOGLE_API_KEY") if provider == "gemini" else None)
    result = {"mode": mode, "role": role, "provider": provider, "retrieval_ms": round(t_retrieval, 1),
              "sources": ctx["sources"], "facts": ctx["facts"], "withheld": ctx["withheld"], "cypher": ctx["cypher"],
              "context_chars": len(ctx["context"])}
    if not key:
        return {**result, "answer": None, "error": "No LLM key available: showing retrieved context only.",
                "context": ctx["context"]}
    t1 = time.perf_counter()
    msg, model, fallbacks = invoke_with_fallback(provider, key, [("system", SYSTEM), ("human", f"CONTEXT:\n{ctx['context']}\n\nQUESTION: {question}")])
    text = msg.content if isinstance(msg.content, str) else "".join(
        p.get("text", "") for p in msg.content if isinstance(p, dict))
    usage = getattr(msg, "usage_metadata", None) or {}
    tin, tout = usage.get("input_tokens", 0), usage.get("output_tokens", 0)
    pin, pout = PRICES.get(provider, (0, 0))
    ctx_ids, cited = set(entity_ids(ctx["context"])), set(entity_ids(text))
    return {**result, "answer": text, "model": model, "fallbacks": fallbacks, "llm_ms": round((time.perf_counter() - t1) * 1000),
            "tokenomics": {"input_tokens": tin, "output_tokens": tout,
                           "cost_usd": round(tin / 1e6 * pin + tout / 1e6 * pout, 6),
                           "context_ids": len(ctx_ids), "cited_ids": len(cited & ctx_ids),
                           "context_efficiency": round(len(cited & ctx_ids) / max(1, len(ctx_ids)), 3)}}
