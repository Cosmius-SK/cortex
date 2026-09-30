"""Record a captioned, silent walkthrough of the live Cortex Space (follows docs/DEMO_SCRIPT.md).

Prerequisite: the owner has asked the scripted questions once (answers are cached, so no PIN is needed here).
Usage: python docs/record_demo.py [--url https://sk-aiu-cortex.hf.space] [--out docs/video]
Needs: pip install playwright (uses the local Chromium).
"""
import argparse
import glob
from pathlib import Path

from playwright.sync_api import sync_playwright

Q1 = "Which controls, procedures and open audit findings are affected by the EU AI Act?"
Q2 = "What must happen before a high-risk AI model is deployed?"
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
    ap.add_argument("--url", default="https://sk-aiu-cortex.hf.space")
    ap.add_argument("--out", default=str(Path(__file__).parent / "video"))
    a = ap.parse_args()
    exe = (glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome") or [None])[0]
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=exe, args=["--no-sandbox"])
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, record_video_dir=a.out,
                            record_video_size={"width": 1440, "height": 900})
        pg = ctx.new_page()
        cap = lambda t, wait=3500: (pg.evaluate(CAPTION_JS, t), pg.wait_for_timeout(wait))
        scroll = lambda y: pg.evaluate(f"window.scrollTo({{top:{y},behavior:'smooth'}})")

        pg.goto(a.url)
        pg.wait_for_selector("#warm.hidden", state="attached", timeout=300000)
        pg.wait_for_timeout(1500)
        cap("<b>Cortex</b>: why FalkorDB for AI engagements, and more", 3500)
        cap("RAG finds <b>similar text</b>. Real questions need <b>connected facts</b>.", 3500)
        scroll(450); cap("73 bank PDFs · a 1M-node operational graph · all in FalkorDB", 3500); scroll(0)

        pg.click("nav >> text=Ask Cortex")
        pg.fill("#q", Q1); pg.click("#askBtn")
        pg.wait_for_selector("#answers .card .ans", timeout=120000); pg.wait_for_timeout(1200)
        cap("Same PDFs, same LLM, same question. Left: today's vector RAG. Right: GraphRAG on FalkorDB.", 4500)
        scroll(520); cap("GraphRAG follows the links: regulation → policies → controls → procedures → findings.", 5000)
        scroll(900); cap("Every answer shows its sources and tokenomics.", 4000); scroll(0)

        pg.click("nav >> text=Engineer view"); pg.wait_for_timeout(1500)
        scroll(520); cap("Measured on 34 questions with known answers: <b>95% vs 72%</b> recall, <b>31 vs 20</b> fully correct.", 5500)
        cap("Multi-hop questions: <b>93% vs 51%</b>, at about the same tokens per correct answer.", 4500); scroll(0)

        pg.click("nav >> text=Ask Cortex")
        pg.check("input[name=cmp][value=roles]"); pg.select_option("#role", "ROLE-CRO"); pg.select_option("#role2", "ROLE-TELLER")
        pg.fill("#q", Q2); pg.click("#askBtn")
        pg.wait_for_selector("#answers .card .ans", timeout=120000); pg.wait_for_timeout(1200)
        scroll(480); cap("Role-aware AI: a Chief Risk Officer and a Branch Teller ask the same question.", 4500)
        cap("Restricted sources are filtered in the graph, so they never reach the LLM.", 4500); scroll(0)

        pg.click("nav >> text=Scenarios"); pg.select_option("#role", "ROLE-COMPLIANCE")
        pg.click("text=5 · Fraud rings"); pg.wait_for_selector("#scOut h2", timeout=60000); pg.wait_for_timeout(1000)
        cap("…and more: 60 hidden fraud rings across 1,005,040 nodes, in under 2 seconds, with zero false alarms.", 5500)
        pg.select_option("#role", "ROLE-TELLER"); pg.click("text=5 · Fraud rings"); pg.wait_for_timeout(1500)
        cap("The same request as a Branch Teller is denied.", 3500)

        pg.select_option("#role", "ROLE-CRO"); pg.click("text=1 · Regulatory impact"); pg.wait_for_timeout(2000)
        cap("A regulation lands: everything it touches, in one sub-millisecond query.", 4500)
        pg.click("text=6 · Risk roll-up"); pg.wait_for_timeout(2000)
        cap("From a single control up to a bank-wide risk score.", 4000)
        pg.click("text=Graph explorer"); pg.wait_for_timeout(3500)
        cap("Explore the knowledge graph behind every answer.", 4000)

        pg.click("nav >> text=Overview"); scroll(0)
        cap("Try it yourself: <b>sk-aiu-cortex.hf.space</b> · 100% synthetic data · $0 to run", 5000)
        path = pg.video.path()
        ctx.close(); b.close()
        print(path)


if __name__ == "__main__":
    main()
