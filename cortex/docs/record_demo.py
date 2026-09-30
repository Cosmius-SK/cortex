"""Record a captioned, silent walkthrough of the live Cortex Space (follows docs/DEMO_SCRIPT.md).

Prerequisite: the owner has asked the scripted questions once (answers are cached, so no PIN is needed here).
Usage: python docs/record_demo.py [--mode exec|full] [--url https://sk-aiu-cortex.hf.space] [--out docs/video]
  exec: ~3 min executive highlights · full: ~6 min tour of every menu (Scenarios, Upload, Engineer view, Limits, Settings)
Needs: pip install playwright (uses the local Chromium).
"""
import argparse
import glob
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

Q1 = "Which controls, procedures and open audit findings are affected by the EU AI Act?"
Q2 = "What must happen before a high-risk AI model is deployed?"
PDF = Path(__file__).resolve().parent.parent / "pdfs" / "AR-2026-04.pdf"
Q3 = "Which KRIs are in breach and which controls do they measure?"

CAPTION_JS = """t => { let c = document.getElementById('rec-cap');
  if (!c) { c = document.createElement('div'); c.id = 'rec-cap';
    c.style.cssText = 'position:fixed;left:50%;bottom:26px;transform:translateX(-50%);max-width:80%;z-index:99;' +
      'background:rgba(11,27,58,.92);color:#fff;font:600 20px/1.4 Inter,Arial,sans-serif;padding:12px 22px;' +
      'border-radius:14px;box-shadow:0 8px 30px rgba(0,0,0,.25);text-align:center';
    document.body.appendChild(c); }
  c.innerHTML = t; c.style.display = t ? 'block' : 'none'; }"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["exec", "full"], default="exec")
    ap.add_argument("--url", default="https://sk-aiu-cortex.hf.space")
    ap.add_argument("--out", default=str(Path(__file__).parent / "video"))
    a = ap.parse_args()
    exe = (glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome") or [None])[0]
    with sync_playwright() as p:
        # Behind a TLS-inspecting proxy, set REC_TRUST_SPKI to that proxy CA's SPKI hash so Chromium trusts it.
        extra = [f"--ignore-certificate-errors-spki-list={os.environ['REC_TRUST_SPKI']}"] if os.getenv("REC_TRUST_SPKI") else []
        b = p.chromium.launch(executable_path=exe, args=["--no-sandbox", *extra])
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, record_video_dir=a.out,
                            record_video_size={"width": 1440, "height": 900})
        pg = ctx.new_page()
        full = a.mode == "full"
        cap = lambda t, wait=3500: (pg.evaluate(CAPTION_JS, t), pg.wait_for_timeout(wait))
        def sc(btn, text, wait=4500):
            cap("", 0); pg.click(f"button:has-text('{btn}')"); settle(); cap(text, wait)

        def settle():
            pg.wait_for_timeout(600)
            pg.wait_for_function("!document.querySelector('#scOut .spin') && !/Running/.test(document.querySelector('#scOut').innerText)", timeout=120000)
            pg.wait_for_timeout(1200)

        def go(name):
            cap("", 0); pg.click(f"nav >> text={name}"); pg.wait_for_timeout(1500)

        scroll = lambda y: pg.evaluate(f"window.scrollTo({{top:{y},behavior:'smooth'}})")

        pg.goto(a.url)
        pg.wait_for_selector("#warm.hidden", state="attached", timeout=300000)
        pg.wait_for_timeout(1500)
        cap("<b>Cortex</b>: why FalkorDB for AI engagements, and more", 3500)
        cap("RAG finds <b>similar text</b>. Real questions need <b>connected facts</b>.", 3500)
        scroll(450); cap("73 bank PDFs · a 1M-node operational graph · all in FalkorDB", 3500); scroll(0)

        go("Ask Cortex")
        pg.fill("#q", Q1); pg.click("#askBtn")
        pg.wait_for_selector("#answers .card .ans", timeout=120000); pg.wait_for_timeout(1200)
        cap("Same PDFs, same LLM, same question. Left: today's vector RAG. Right: GraphRAG on FalkorDB.", 4500)
        scroll(520); cap("GraphRAG follows the links: regulation → policies → controls → procedures → findings.", 5000)
        scroll(900); cap("Every answer shows its sources and tokenomics.", 4000); scroll(0)

        go("Engineer view")
        scroll(600); cap("Measured on 34 questions with known answers: <b>97% vs 70%</b> recall, <b>31 vs 19</b> fully correct.", 5500)
        cap("Multi-hop questions: <b>97% vs 47%</b>, at the same tokens per correct answer (2,535 vs 2,540).", 4500); scroll(0)

        go("Ask Cortex")
        pg.check("input[name=cmp][value=roles]"); pg.select_option("#role", "ROLE-CRO"); pg.select_option("#role2", "ROLE-TELLER")
        pg.fill("#q", Q2); pg.click("#askBtn")
        pg.wait_for_selector("#answers .card .ans", timeout=120000); pg.wait_for_timeout(1200)
        scroll(480); cap("Role-aware AI: a Chief Risk Officer and a Branch Teller ask the same question.", 4500)
        cap("Restricted sources are filtered in the graph, so they never reach the LLM.", 4500); scroll(0)

        go("Scenarios"); pg.select_option("#role", "ROLE-COMPLIANCE")
        cap("", 0); pg.click("text=5 · Fraud rings"); settle()
        cap("…and more: 60 hidden fraud rings across 1,005,040 nodes, in under 2 seconds, with zero false alarms.", 5500)
        pg.select_option("#role", "ROLE-TELLER"); pg.click("text=5 · Fraud rings"); settle()
        cap("The same request as a Branch Teller is denied.", 3500)

        pg.select_option("#role", "ROLE-CRO"); sc("1 · Regulatory impact", "A regulation lands: everything it touches, in one sub-millisecond query.")
        sc("6 · Risk roll-up", "From a single control up to a bank-wide risk score.")
        if full:
            sc("7 · Version history", "Lineage: which procedure superseded which, and what changed.")
        sc("8 · Performance", "FalkorDB execution times on the 1M-node graph, measured live.", 6000)
        sc("Graph explorer", "Explore the knowledge graph behind every answer.")
        if full:
            go("Upload")
            cap("Bring your own PDF: it goes into a private sandbox graph.", 4000)
            pg.set_input_files("#file", str(PDF)); pg.click("text=Ingest into sandbox")
            pg.wait_for_function("document.querySelector('#upMsg').textContent && !document.querySelector('#upMsg .spin')", timeout=180000)
            pg.wait_for_timeout(1500)
            cap("Entities and relationships extracted; the sandbox wipes itself after 24 hours.", 5500)
            go("Engineer view")
            cap("Pipeline: LangChain loader and splitter, local embeddings, pattern extraction (295/295 correct, 0 tokens).", 5500)
            scroll(900); cap("Every retrieval query is visible: the exact Cypher behind each answer.", 5000); scroll(0)
            go("Limits")
            cap("Nothing is limited silently: quotas, PIN, sandbox wipe and idle reset are all published.", 5500)
            scroll(600); pg.wait_for_timeout(2500); scroll(0)
            pg.click("header >> button:has-text('Settings')"); pg.wait_for_timeout(1200)
            cap("Settings: shared free Gemini with an access PIN, or bring your own Gemini / Claude key, encrypted in your browser.", 6000)
            pg.click("#settings >> text=Close"); pg.wait_for_timeout(800)

        go("Overview"); scroll(0)
        cap("Try it yourself: <b>sk-aiu-cortex.hf.space</b> · 100% synthetic data · $0 to run", 5000)
        path = pg.video.path()
        ctx.close(); b.close()
        dst = Path(a.out) / f"cortex-{a.mode}.webm"; Path(path).rename(dst); print(dst); return
        ctx.close(); b.close()
        print(path)


if __name__ == "__main__":
    main()
