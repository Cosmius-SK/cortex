"""Render the Cortex Bank knowledge base into realistic PDF documents.

Usage: python -m generator.render_pdfs   (run from cortex/)
Outputs: pdfs/*.pdf, pdfs/manifest.json
"""
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from content import bank as B

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "pdfs"
LOGO = ROOT / "docs" / "brand" / "cortex-logo.png"

NAVY = colors.HexColor("#0B1B3A")
ORANGE = colors.HexColor("#F97316")
GREY = colors.HexColor("#64748B")
LEVEL_LABEL = {0: "L0 PUBLIC / CONTRACTOR", 1: "L1 INTERNAL", 2: "L2 CONFIDENTIAL", 3: "L3 RESTRICTED", 4: "L4 HIGHLY RESTRICTED"}

ss = getSampleStyleSheet()
S = {
    "title": ParagraphStyle("t", parent=ss["Title"], textColor=NAVY, fontSize=18, leading=22, alignment=0, spaceAfter=4),
    "h": ParagraphStyle("h", parent=ss["Heading2"], textColor=NAVY, fontSize=12, spaceBefore=10, spaceAfter=4),
    "p": ParagraphStyle("p", parent=ss["BodyText"], fontSize=9.5, leading=13),
    "small": ParagraphStyle("s", parent=ss["BodyText"], fontSize=8, textColor=GREY),
    "cls": ParagraphStyle("c", parent=ss["BodyText"], fontSize=8, textColor=ORANGE, alignment=TA_RIGHT),
}

DEPT = {d[0]: d for d in B.DEPARTMENTS}
REG = {r[0]: r for r in B.REGULATIONS}
CTL = {c[0]: c for c in B.CONTROLS}
RISK = {r[0]: r for r in B.RISKS}
SYS = {s[0]: s for s in B.SYSTEMS}
POL = {p[0]: p for p in B.POLICIES}


def reg(rid):
    return f"{REG[rid][1]} ({rid})"


def ctl(cid):
    return f"{CTL[cid][1]} ({cid})"


def sysn(sid):
    return f"{SYS[sid][1]} ({sid})"


def dept(code):
    return f"{DEPT[code][1]} ({code})"


def table(rows, widths, header=True):
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
             ("VALIGN", (0, 0), (-1, -1), "TOP")]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
    t.setStyle(TableStyle(style))
    return t


def P(text, style="p"):
    return Paragraph(text, S[style])


def bullets(items):
    return [P(f"&bull; {i}") for i in items]


class Doc:
    def __init__(self, doc_id, title, doc_type, dept_code, level, version, effective, owner=None):
        self.id, self.title, self.type, self.dept, self.level = doc_id, title, doc_type, dept_code, level
        self.version, self.effective = version, effective
        self.owner = owner or DEPT[dept_code][2]
        self.body = []

    def meta(self):
        return {"id": self.id, "title": self.title, "type": self.type, "dept": self.dept, "level": self.level,
                "version": self.version, "effective": self.effective, "file": f"{self.id}.pdf"}

    def render(self):
        path = OUT / f"{self.id}.pdf"
        cls = LEVEL_LABEL[self.level]

        def frame(canvas, doc):
            canvas.saveState()
            if LOGO.exists():
                canvas.drawImage(str(LOGO), 18 * mm, 277 * mm, 12 * mm, 12 * mm, mask="auto")
            canvas.setFont("Helvetica-Bold", 11)
            canvas.setFillColor(NAVY)
            canvas.drawString(32 * mm, 284 * mm, "CORTEX BANK")
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(GREY)
            canvas.drawString(32 * mm, 280 * mm, f"{B.BANK['tagline']}  |  {B.BANK['hq']}")
            canvas.setFillColor(ORANGE)
            canvas.setFont("Helvetica-Bold", 8)
            canvas.drawRightString(192 * mm, 284 * mm, cls)
            canvas.setFillColor(GREY)
            canvas.setFont("Helvetica", 7)
            canvas.drawRightString(192 * mm, 280 * mm, f"{self.id}  v{self.version}")
            canvas.line(18 * mm, 276 * mm, 192 * mm, 276 * mm)
            canvas.drawString(18 * mm, 10 * mm, f"{cls}  -  Synthetic document for demonstration. Not a real bank.")
            canvas.drawRightString(192 * mm, 10 * mm, f"Page {doc.page}")
            canvas.restoreState()

        head = [P(self.title, "title"),
                table([["Document ID", self.id, "Type", self.type],
                       ["Owner", f"{self.owner}, {DEPT[self.dept][1]}", "Classification", cls],
                       ["Version", self.version, "Effective", self.effective]],
                      [28 * mm, 62 * mm, 28 * mm, 56 * mm], header=False),
                Spacer(1, 6)]
        SimpleDocTemplate(str(path), pagesize=A4, topMargin=26 * mm, bottomMargin=18 * mm,
                          leftMargin=18 * mm, rightMargin=18 * mm, title=self.title,
                          author="Cortex Bank (synthetic)").build(head + self.body, onFirstPage=frame, onLaterPages=frame)


def approval(d, approver):
    return [P("Approval", "h"), table([["Approved by", "Date"], [approver, d.effective]], [120 * mm, 54 * mm])]


def related(ids):
    return [P("Related Documents", "h"), P(", ".join(ids))] if ids else []


def build_policy(p):
    pid, title, dcode, regs, ctls, stmts, ver, eff, lvl = p
    d = Doc(pid, title, "Policy", dcode, lvl, ver, eff)
    sops = [s[0] for s in B.SOPS if pid in s[3]]
    grds = [g[0] for g in B.GUARDRAILS if pid in g[3]]
    risks = sorted({r for c in ctls for r in CTL[c][5]})
    d.body += [P("1. Purpose", "h"),
               P(f"This policy sets out Cortex Bank's requirements for {title.replace(' Policy', '')}. "
                 f"It is owned by the {d.owner} in {dept(dcode)} and applies to all staff, contractors and subsidiaries.")]
    if regs:
        d.body += [P("2. Regulatory Basis", "h"),
                   P("This policy implements the bank's obligations under " + "; ".join(reg(r) for r in regs) + "."),
                   *bullets(f"{REG[r][1]}: {REG[r][3]}" for r in regs)]
    d.body += [P("3. Policy Statements", "h"), *bullets(stmts)]
    if ctls:
        d.body += [P("4. Key Controls", "h"),
                   P("Compliance with this policy is achieved through the following controls:"),
                   table([["Control", "Name", "Type", "Frequency", "Owner", "Mitigates"]] +
                         [[c, Paragraph(CTL[c][1], S["p"]), CTL[c][2], CTL[c][3], CTL[c][4], ", ".join(CTL[c][5])] for c in ctls],
                         [22 * mm, 62 * mm, 20 * mm, 22 * mm, 14 * mm, 34 * mm])]
    if risks:
        d.body += [P("5. Risks Addressed", "h"), P(", ".join(f"{RISK[r][1]} ({r})" for r in risks) + ".")]
    if sops:
        d.body += [P("6. Implementing Procedures", "h"), P("This policy is implemented by: " + ", ".join(sops) + ".")]
    if grds:
        d.body += [P("7. Applicable Standards", "h"), P("The following guardrail standards apply: " + ", ".join(grds) + ".")]
    d.body += related(sops + grds + regs) + approval(d, "Board Risk Committee" if lvl >= 2 else DEPT[dcode][2])
    return d


def build_sop(s):
    sid, title, dcode, pols, systems, steps, ver, eff, lvl = s
    d = Doc(sid, title, "Standard Operating Procedure", dcode, lvl, ver, eff)
    legacy = [l for l in B.LEGACY_SOPS if l[6] == sid]
    grds = [g[0] for g in B.GUARDRAILS if sid in g[3]]
    d.body += [P("1. Purpose and Scope", "h"),
               P(f"This procedure describes how {DEPT[dcode][1]} performs '{title}'. "
                 f"It implements " + ", ".join(f"{POL[p][1]} ({p})" for p in pols) + ".")]
    if systems:
        d.body += [P("2. Systems Used", "h"), *bullets(f"{sysn(x)}: {SYS[x][2]}" for x in systems)]
    rows = [["Step", "Activity", "Controls"]]
    for i, (text, cs) in enumerate(steps, 1):
        rows.append([str(i), Paragraph(text, S["p"]), Paragraph("<br/>".join(ctl(c) for c in cs) or "-", S["p"])])
    d.body += [P("3. Procedure", "h"), table(rows, [12 * mm, 100 * mm, 62 * mm])]
    if grds:
        d.body += [P("4. Guardrails", "h"), P("This procedure is subject to: " + ", ".join(grds) + ".")]
    vh = [["Version", "Effective", "Change"]]
    for l in legacy:
        vh.append([l[3], l[4], f"Original procedure ({l[0]}), retired {l[5]}."])
    vh.append([ver, eff, "Current version." + (f" Supersedes {legacy[0][0]}." if legacy else "")])
    d.body += [P("5. Version History", "h"), table(vh, [18 * mm, 24 * mm, 132 * mm])]
    d.body += related(pols + grds + [l[0] for l in legacy]) + approval(d, DEPT[dcode][2])
    return d


def build_legacy(l):
    lid, title, dcode, ver, eff, retired, sup, summary, lvl = l
    d = Doc(lid, title, "Standard Operating Procedure (Retired)", dcode, lvl, ver, eff)
    d.body += [P("STATUS: RETIRED", "h"),
               P(f"This procedure was in force from {eff} until {retired}. It is superseded by {sup}. Retained for record-keeping only."),
               P("1. Procedure Summary", "h"), P(summary)] + related([sup])
    return d


def build_guardrail(g):
    gid, title, dcode, applies, rules, lvl = g
    d = Doc(gid, title, "Guardrail Standard", dcode, lvl, "1.0", "2025-01-01")
    d.body += [P("1. Purpose", "h"), P(f"This standard defines mandatory guardrails. Owner: {dept(dcode)}."),
               P("2. Mandatory Rules", "h"), *bullets(rules),
               P("3. Applies To", "h"), P(", ".join(applies) + ".")]
    if gid == "GRD-004":
        rows = [["Role", "Clearance", "Department scope"]] + [[r[1], f"L{r[2]}", ", ".join(r[3])] for r in B.ROLES]
        d.body += [P("4. Role Access Matrix", "h"), table(rows, [70 * mm, 30 * mm, 74 * mm])]
    return d


def build_kri(k):
    kid, title, dcode, lvl, inds = k
    d = Doc(kid, title, "KRI / KPI Framework", dcode, lvl, "2026.Q2", "2026-06-30")
    rows = [["Indicator", "Name", "Measures", "Target", "Current", "Status"]]
    rows += [[i[0], Paragraph(i[1], S["p"]), ", ".join(i[2]), i[3], i[4], i[5]] for i in inds]
    breaches = [i for i in inds if i[5] == "Breach"]
    d.body += [P("1. Purpose", "h"), P(f"Key indicators monitored by {dept(dcode)} and reported quarterly to the Board Risk Committee."),
               P("2. Indicators (as at 30 June 2026)", "h"),
               table(rows, [20 * mm, 62 * mm, 26 * mm, 20 * mm, 20 * mm, 26 * mm])]
    if breaches:
        d.body += [P("3. Breaches Requiring Action", "h"),
                   *bullets(f"{i[0]} ({i[1]}) is in breach: {i[4]} against a target of {i[3]}. Linked control: {', '.join(ctl(c) for c in i[2])}." for i in breaches)]
    return d


def build_audit(a):
    aid, title, date, lvl, scope, findings = a
    d = Doc(aid, title, "Internal Audit Report", "IAU", lvl, "Final", date)
    rating = "Unsatisfactory" if any(f[2] == "High" for f in findings) else "Needs Improvement"
    d.body += [P("1. Executive Summary", "h"),
               P(f"Internal Audit reviewed {', '.join(dept(s) for s in scope)}. Overall rating: <b>{rating}</b>. "
                 f"{len(findings)} finding(s) raised, reported to the Board Audit Committee."),
               P("2. Findings", "h")]
    for f in findings:
        d.body += [P(f"<b>{f[0]}: {f[1]}</b>"),
                   P(f"Severity: {f[2]}. Control: {ctl(f[3])}. Owner: {dept(f[4])}. Remediation due: {f[5]}. Status: {f[6]}."),
                   Spacer(1, 4)]
    return d


def build_regsum(r):
    rid, short, full, summary = r
    pols = [p for p in B.POLICIES if rid in p[3]]
    d = Doc(f"RS-{rid[4:]}", f"Regulatory Obligation Summary: {short}", "Regulatory Summary", "LGL", 1, "2026.1", "2026-01-10")
    d.body += [P("1. Regulation", "h"), P(f"{full} ({rid}). {summary}"),
               P("2. How Cortex Bank Complies", "h"),
               table([["Policy", "Title", "Owner"]] + [[p[0], Paragraph(p[1], S["p"]), p[2]] for p in pols],
                     [28 * mm, 110 * mm, 36 * mm])]
    return d


def build_rcn(c):
    cid, title, date, rid, summary, pols, actions = c
    d = Doc(cid, title, "Regulatory Change Notice", "LGL", 1, "1.0", date)
    d.body += [P("1. Change", "h"), P(f"{summary} Regulation: {reg(rid)}."),
               P("2. Impacted Policies", "h"), *bullets(f"{POL[p][1]} ({p})" for p in pols),
               P("3. Required Actions", "h"), *bullets(actions)]
    return d


def build_history():
    d = Doc("HIS-001", "Cortex Bank: A Century of Banking (1926-2026)", "Corporate History", "LGL", 1, "1.0", "2026-01-01")
    d.body += [P("Milestones", "h"), table([["Year", "Event"]] + [[str(y), Paragraph(e, S["p"])] for y, e in B.HISTORY], [20 * mm, 154 * mm]),
               P("Legacy Systems Still in Use", "h"), *bullets(f"{sysn(s[0])}: {s[2]}" for s in B.SYSTEMS if s[0] in ("SYS-CORE", "SYS-TRD"))]
    return d


def build_org():
    d = Doc("ORG-001", "Organisation & Department Mandates", "Organisation Chart", "HRS", 1, "2026.1", "2026-01-01")
    d.body += [P("Departments", "h"),
               table([["Code", "Department", "Head", "Mandate"]] + [[x[0], x[1], x[2], Paragraph(x[3], S["p"])] for x in B.DEPARTMENTS],
                     [14 * mm, 44 * mm, 40 * mm, 76 * mm])]
    return d


def all_docs():
    docs = [build_policy(p) for p in B.POLICIES] + [build_sop(s) for s in B.SOPS]
    docs += [build_legacy(l) for l in B.LEGACY_SOPS] + [build_guardrail(g) for g in B.GUARDRAILS]
    docs += [build_kri(k) for k in B.KRI_FRAMEWORKS] + [build_audit(a) for a in B.AUDIT_REPORTS]
    docs += [build_regsum(r) for r in B.REGULATIONS] + [build_rcn(c) for c in B.CHANGE_NOTICES]
    docs += [build_history(), build_org()]
    return docs


def main():
    OUT.mkdir(exist_ok=True)
    docs = all_docs()
    for d in docs:
        d.render()
    (OUT / "manifest.json").write_text(json.dumps([d.meta() for d in docs], indent=1))
    print(f"Rendered {len(docs)} PDFs to {OUT}")


if __name__ == "__main__":
    main()
