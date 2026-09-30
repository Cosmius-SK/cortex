"""Cortex web server: FastAPI API + static UI.

Security & limits (DESIGN.md §11) are enforced here and published at /api/limits.
"""
import hmac
import os
import secrets
import tempfile
import threading
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.bootstrap import STATUS, start_background
from content import bank as B

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).resolve().parent / "static"

LIMITS = {
    "pin_session_hours": 8, "pin_max_failures": 5, "pin_lockout_minutes": 15,
    "questions_per_session_per_day": int(os.getenv("CORTEX_Q_PER_SESSION", "20")),
    "questions_per_day_total": int(os.getenv("CORTEX_Q_PER_DAY", "200")),
    "question_max_chars": 500,
    "upload_max_mb": 5, "upload_max_pages": 20, "uploads_per_session": 3, "sandbox_ttl_hours": 24,
    "idle_reset_hours": 4,
}
SESSIONS, LOCKS, CACHE = {}, {}, {}
DAY = {"date": time.strftime("%Y-%m-%d"), "count": 0}
LAST_ACTIVITY = {"t": time.time()}
LOCK = threading.Lock()

app = FastAPI(title="Cortex", docs_url=None, redoc_url=None)


# ---------- sessions, PINs, quotas ----------
def session(sid):
    LAST_ACTIVITY["t"] = time.time()
    s = SESSIONS.get(sid or "")
    if not s:
        raise HTTPException(401, "Session expired. Reload the page.")
    s["last"] = time.time()
    return s


@app.post("/api/session")
def new_session():
    sid = secrets.token_urlsafe(18)
    SESSIONS[sid] = {"created": time.time(), "last": time.time(), "pin_until": 0, "asked": 0, "uploads": []}
    return {"session": sid}


@app.post("/api/unlock")
def unlock(request: Request, pin: str = Form(...), x_session: str = Header(None)):
    s = session(x_session)
    ip = request.client.host if request.client else "?"
    lock = LOCKS.setdefault(ip, {"fails": 0, "until": 0})
    if lock["until"] > time.time():
        raise HTTPException(429, f"Too many attempts. Try again in {int((lock['until'] - time.time()) / 60) + 1} min.")
    expected = os.getenv("CORTEX_ACCESS_PIN", "")
    if expected and hmac.compare_digest(pin.strip(), expected):
        lock["fails"] = 0
        s["pin_until"] = time.time() + LIMITS["pin_session_hours"] * 3600
        return {"ok": True, "valid_hours": LIMITS["pin_session_hours"]}
    lock["fails"] += 1
    if lock["fails"] >= LIMITS["pin_max_failures"]:
        lock.update(fails=0, until=time.time() + LIMITS["pin_lockout_minutes"] * 60)
    raise HTTPException(403, "Incorrect PIN." if expected else "Access PIN not configured by the owner.")


def llm_access(s, provider, byok):
    """Returns (provider, api_key). BYOK needs no PIN; the shared key needs a PIN session and quota."""
    if byok:
        return provider, byok
    if s["pin_until"] < time.time():
        raise HTTPException(403, "Enter the Access PIN to use the shared free model, or add your own key in Settings.")
    with LOCK:
        today = time.strftime("%Y-%m-%d")
        if DAY["date"] != today:
            DAY.update(date=today, count=0)
            for x in SESSIONS.values():
                x["asked"] = 0
        if s["asked"] >= LIMITS["questions_per_session_per_day"]:
            raise HTTPException(429, "You've used today's shared questions. Add your own key in Settings to continue.")
        if DAY["count"] >= LIMITS["questions_per_day_total"]:
            raise HTTPException(429, "The shared daily limit is reached. Add your own key in Settings to continue.")
        s["asked"] += 1
        DAY["count"] += 1
    return "gemini", None


def quota(s):
    return {"asked": s["asked"], "limit": LIMITS["questions_per_session_per_day"],
            "pin_active": s["pin_until"] > time.time(), "pin_expires_in_min": max(0, int((s["pin_until"] - time.time()) / 60))}


# ---------- read-only info ----------
@app.get("/api/status")
def status():
    return STATUS


@app.get("/api/limits")
def limits():
    return LIMITS


@app.get("/api/roles")
def roles():
    return [{"id": r[0], "name": r[1], "clearance": r[2], "scope": r[3]} for r in B.ROLES]


@app.get("/api/me")
def me(x_session: str = Header(None)):
    s = session(x_session)
    return {**quota(s), "sandboxes": [{k: u[k] for k in ("graph", "title", "expires")} for u in s["uploads"]]}


def ready():
    if not STATUS["ready"]:
        raise HTTPException(503, "Cortex is warming up. Please wait a moment.")


# ---------- ask ----------
@app.post("/api/ask")
async def ask(request: Request, x_session: str = Header(None)):
    ready()
    body = await request.json()
    s = session(x_session)
    q = (body.get("question") or "").strip()
    if not q or len(q) > LIMITS["question_max_chars"]:
        raise HTTPException(400, f"Questions must be 1-{LIMITS['question_max_chars']} characters.")
    mode, role = body.get("mode", "graph"), body.get("role") or None
    graph_name = body.get("graph") or "cortex_kg"
    if graph_name != "cortex_kg" and graph_name not in {u["graph"] for u in s["uploads"]}:
        raise HTTPException(403, "That sandbox belongs to another session.")
    byok = (body.get("api_key") or "").strip() or None
    key = (q.lower(), mode, role, graph_name)
    if not byok and graph_name == "cortex_kg" and key in CACHE:
        return {**CACHE[key], "cached": True, "quota": quota(s)}
    provider, api_key = llm_access(s, body.get("provider", "gemini"), byok)
    from core.llm import answer
    try:
        res = answer(q, mode, role, provider, api_key, graph_name)
    except Exception as e:  # provider errors: bad key, rate limit, safety block
        detail = str(e).replace(api_key or "\0", "***").replace(os.getenv("GOOGLE_API_KEY") or "\0", "***")[:180]
        raise HTTPException(502, f"The model provider returned an error: {type(e).__name__}: {detail}")
    if not byok and not res.get("answer"):  # nothing was generated: refund the shared quota
        with LOCK:
            s["asked"] -= 1
            DAY["count"] -= 1
    if not byok and res.get("answer") and graph_name == "cortex_kg":
        CACHE[key] = res
    return {**res, "cached": False, "quota": quota(s)}


# ---------- scenarios (pure Cypher: free) ----------
@app.get("/api/scenario/{name}")
def scenario(name: str, role: str = "ROLE-CRO", reg: str = "REG-EUAI", center: str = "POL-AI-001", x_session: str = Header(None)):
    ready()
    session(x_session)
    from core import retrieval, scenarios
    fn = {"impact": lambda: retrieval.impact(reg, role), "fraud": lambda: scenarios.fraud(role),
          "rollup": lambda: scenarios.rollup(role), "versions": lambda: scenarios.versions(role),
          "perf": scenarios.perf, "graph": lambda: scenarios.neighborhood(center, role)}.get(name)
    if not fn:
        raise HTTPException(404, "Unknown scenario.")
    return fn()


# ---------- X-Ray: live FalkorDB internals (read-only, free) ----------
XRAY = {"t": 0, "data": None}


@app.get("/api/xray")
def xray_overview(x_session: str = Header(None)):
    ready()
    session(x_session)
    from core import xray
    if time.time() - XRAY["t"] > 60:  # counting 4.8M edges per type is cheap, but not per click
        XRAY.update(t=time.time(), data=xray.overview())
    return XRAY["data"]


@app.get("/api/xray/plan/{name}")
def xray_plan(name: str, x_session: str = Header(None)):
    ready()
    session(x_session)
    from core import xray
    if name not in xray.PLAN_QUERIES:
        raise HTTPException(404, "Unknown query.")
    return xray.plan(name)


# ---------- evaluation (shared model, PIN required, max once per 6 hours) ----------
EVAL = {"status": None, "result": None, "started": 0}
_EVAL_FILE = ROOT / "eval" / "results.json"
if _EVAL_FILE.exists():
    try:
        import json as _json
        EVAL["result"] = _json.loads(_EVAL_FILE.read_text())
        EVAL["status"] = EVAL["result"].pop("status", None)  # saved run survives restarts
    except Exception:
        pass


@app.get("/api/eval")
def eval_status(x_session: str = Header(None)):
    session(x_session)
    r = EVAL["result"] or {}
    return {"status": EVAL["status"], **{k: r.get(k) for k in ("summary", "model", "role", "finished")}}


@app.post("/api/eval")
def eval_start(x_session: str = Header(None)):
    ready()
    s = session(x_session)
    if s["pin_until"] < time.time():
        raise HTTPException(403, "Enter the Access PIN in Settings to run the evaluation.")
    if EVAL["status"] and EVAL["status"].startswith("running"):
        return {"message": EVAL["status"]}
    if time.time() - EVAL["started"] < 6 * 3600 and EVAL["result"]:
        raise HTTPException(429, "The evaluation already ran in the last 6 hours; results are shown below.")
    EVAL.update(status="running: starting", started=time.time())

    def job():
        from eval.run_eval import run
        try:
            res = run(progress=lambda m: EVAL.update(status=m))
            EVAL.update(result=res, status=f"finished {res['finished']}")
            try:
                import json as _json
                _EVAL_FILE.write_text(_json.dumps(res, indent=1))
            except Exception:
                pass
        except Exception as e:
            EVAL.update(status=f"failed: {type(e).__name__}")

    threading.Thread(target=job, daemon=True).start()
    return {"message": "Evaluation started: about 5-8 minutes. This panel refreshes by itself."}


# ---------- uploads -> private sandbox graph ----------
@app.post("/api/upload")
async def upload(file: UploadFile = File(...), provider: str = Form("gemini"), api_key: str = Form(""),
                 x_session: str = Header(None)):
    ready()
    s = session(x_session)
    if len(s["uploads"]) >= LIMITS["uploads_per_session"]:
        raise HTTPException(429, f"Maximum {LIMITS['uploads_per_session']} uploads per session.")
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "PDF files only.")
    data = await file.read(LIMITS["upload_max_mb"] * 1024 * 1024 + 1)
    if len(data) > LIMITS["upload_max_mb"] * 1024 * 1024:
        raise HTTPException(413, f"Maximum {LIMITS['upload_max_mb']} MB.")
    from pypdf import PdfReader
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(data)
        tmp.flush()
        try:
            reader = PdfReader(tmp.name)
            pages = len(reader.pages)
            text = "\n".join((p.extract_text() or "") for p in reader.pages[: LIMITS["upload_max_pages"]])
        except Exception:
            raise HTTPException(400, "Could not read this PDF.")
    if pages > LIMITS["upload_max_pages"]:
        raise HTTPException(400, f"Maximum {LIMITS['upload_max_pages']} pages (this file has {pages}).")
    if len(text.strip()) < 50:
        raise HTTPException(400, "No extractable text found (scanned PDFs are not supported).")
    gname = f"sandbox_{secrets.token_hex(6)}"
    doc = {"id": "UPLOAD-1", "title": Path(file.filename).stem[:80], "type": "Upload", "dept": "SANDBOX", "level": 0, "text": text}
    note, usage = "Pattern extraction only (no LLM access: enter the PIN or add your own key for LLM extraction).", {}
    try:
        prov, key = llm_access(s, provider, api_key.strip() or None)
        from core.llm import chat_model
        from ingest.llm_extract import llm_extract
        names, triples, usage = llm_extract(chat_model(prov, key or os.getenv("GOOGLE_API_KEY")), text)
        doc["llm"] = (names, triples)
        note = f"LLM extraction: {len(names)} entities, {len(triples)} relationships."
    except HTTPException:
        pass
    except Exception as e:
        note = f"LLM extraction failed ({type(e).__name__}); pattern extraction used."
    from core.embeddings import LocalEmbeddings
    from ingest.pipeline import ingest, init_schema
    ingest(init_schema(gname), [doc], LocalEmbeddings())
    entry = {"graph": gname, "doc": doc["id"], "title": doc["title"], "created": time.time(),
             "expires": time.time() + LIMITS["sandbox_ttl_hours"] * 3600}
    s["uploads"].append(entry)
    return {"graph": gname, "title": doc["title"], "pages": pages, "note": note, "expires": entry["expires"],
            "tokens": usage, "quota": quota(s)}


# ---------- housekeeping: 24h sandbox wipe + 4h idle reset ----------
def _drop(gname):
    from core.graph import graph
    try:
        graph(gname).delete()
    except Exception:
        pass


def housekeeping():
    while True:
        time.sleep(300)
        now = time.time()
        for s in list(SESSIONS.values()):
            for u in [u for u in s["uploads"] if u["expires"] < now]:
                _drop(u["graph"])
                s["uploads"].remove(u)
        if now - LAST_ACTIVITY["t"] > LIMITS["idle_reset_hours"] * 3600 and SESSIONS:
            for s in SESSIONS.values():
                for u in s["uploads"]:
                    _drop(u["graph"])
            SESSIONS.clear()
            CACHE.clear()
            STATUS["last_idle_reset"] = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())


@app.on_event("startup")
def _startup():
    start_background()
    threading.Thread(target=housekeeping, daemon=True).start()


@app.exception_handler(HTTPException)
async def _err(_, exc):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


app.mount("/static", StaticFiles(directory=STATIC), name="static")
app.mount("/pdfs", StaticFiles(directory=ROOT / "pdfs"), name="pdfs")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")
