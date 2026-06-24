"""Approval-record / discrepancy-report PDF generation (the DHR artifact).

Renders the generated record in the worked-example output shape:
  - header (identity + batch CoC no. + generated date stamp)
  - Section 1: source-of-truth values table (per-document columns)
  - Section 2/3: summary scorecard (Check / Result / Reason)
  - acknowledged flags + the DEFERRED "not machine-verified" list
  - Quality Approval block (signer of record + signature date stamp)

Degrades to None if reportlab is unavailable (it's in backend/requirements.txt).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

RESULT_COLORS = {
    "PASS": "#16a34a", "FAIL": "#dc2626", "FLAG": "#d97706", "DEFERRED": "#6b7280",
}


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def generate_bundle(out_path: str, result: Dict, decision: str, signer_name: str,
                    acknowledged_flags: Optional[List] = None) -> Optional[str]:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                        Paragraph, Spacer)
    except Exception:
        return None

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=15, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=11, spaceBefore=10, spaceAfter=4)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=7.5, leading=9)
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=8.5, leading=11)

    ident = result.get("identity", {})
    generated = _stamp()
    story: List = []

    title = ("Label Approval Record (WI052-F1)" if decision == "RELEASED"
             else "Label Discrepancy Report (WI052 §3.9)")
    story.append(Paragraph(title, h1))
    story.append(Paragraph(
        f"Verdict <b>{result.get('verdict','')}</b> &nbsp;•&nbsp; Decision <b>{decision}</b>"
        f" &nbsp;•&nbsp; Generated {generated}", body))
    story.append(Paragraph(
        f"REF <b>{ident.get('ref','')}</b> &nbsp;•&nbsp; LOT <b>{ident.get('lot','')}</b>"
        f" &nbsp;•&nbsp; Sterile lot <b>{ident.get('sterile_lot','')}</b>"
        f" &nbsp;•&nbsp; Batch CoC #{ident.get('batch_certificate_no','')}", body))
    story.append(Paragraph(
        f"Qty released {ident.get('qty_released','')} &nbsp;•&nbsp; "
        f"Mfg {ident.get('mfg_date','')} &nbsp;•&nbsp; Exp {ident.get('exp_date','')} "
        f"&nbsp;•&nbsp; Rules {result.get('rules_version','')}", body))

    # --- Section 1: source-of-truth table ---
    sot = result.get("source_of_truth") or []
    if sot:
        story.append(Paragraph("Section 1 — Source-of-truth values", h2))
        header = ["Field", "Label", "Batch CoC", "Sterile CoC", "Sterile Lot Record"]
        data = [[Paragraph(f"<b>{c}</b>", small) for c in header]]
        for r in sot:
            data.append([
                Paragraph(r.get("field", ""), small),
                Paragraph(r.get("label", ""), small),
                Paragraph(r.get("batch_coc", ""), small),
                Paragraph(r.get("sterile_coc", ""), small),
                Paragraph(r.get("sterile_lot_record", ""), small),
            ])
        t = Table(data, colWidths=[1.25 * inch, 1.7 * inch, 1.2 * inch, 1.1 * inch, 1.25 * inch])
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
        ]))
        story.append(t)

    # --- Section 2: check-by-check detail (narrative + evidence sub-results) ---
    checks = result.get("checks", [])
    if checks:
        story.append(Paragraph("Section 2 — Check-by-check detail", h2))
        check_head = ParagraphStyle("ch", parent=body, fontSize=9, spaceBefore=7, spaceAfter=2)
        for chk in checks:
            res = chk.get("result", "")
            color = RESULT_COLORS.get(res, "#111827")
            story.append(Paragraph(
                f'<b>Check {chk.get("check_code","")} — {chk.get("check_name","")}</b> '
                f'&nbsp;<b><font color="{color}">{res}</font></b>', check_head))
            if chk.get("reason"):
                story.append(Paragraph(chk["reason"], small))
            subs = chk.get("sub_results") or []
            if subs:
                sd = [[Paragraph("<b>Item</b>", small), Paragraph("<b>Result</b>", small),
                       Paragraph("<b>Detail</b>", small)]]
                for s in subs:
                    sres = s.get("result", "")
                    scolor = RESULT_COLORS.get(sres, "#111827")
                    item = s.get("ai") or s.get("item") or s.get("field") or ""
                    if s.get("ai"):
                        item = f"AI({item})"
                    sd.append([
                        Paragraph(str(item), small),
                        Paragraph(f'<b><font color="{scolor}">{sres}</font></b>', small),
                        Paragraph(str(s.get("reason", "")), small),
                    ])
                sub_t = Table(sd, colWidths=[1.4 * inch, 0.8 * inch, 4.3 * inch])
                sub_t.setStyle(TableStyle([
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e5e7eb")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f9fafb")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]))
                story.append(Spacer(1, 0.03 * inch))
                story.append(sub_t)

    # --- Section 3: scorecard ---
    story.append(Paragraph("Section 3 — Summary scorecard", h2))
    sc = [[Paragraph("<b>Check</b>", small), Paragraph("<b>Name</b>", small),
           Paragraph("<b>Result</b>", small), Paragraph("<b>Reason</b>", small)]]
    for chk in result.get("checks", []):
        color = RESULT_COLORS.get(chk.get("result", ""), "#111827")
        sc.append([
            Paragraph(chk.get("check_code", ""), small),
            Paragraph(chk.get("check_name", ""), small),
            Paragraph(f'<b><font color="{color}">{chk.get("result","")}</font></b>', small),
            Paragraph(chk.get("reason", ""), small),
        ])
    st = Table(sc, colWidths=[0.5 * inch, 1.8 * inch, 0.9 * inch, 3.3 * inch])
    st.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(st)

    # --- acknowledged flags ---
    if acknowledged_flags:
        story.append(Paragraph("Acknowledged flags", h2))
        for f in acknowledged_flags:
            item = f.get("item", f) if isinstance(f, dict) else f
            note = f.get("note", "") if isinstance(f, dict) else ""
            story.append(Paragraph(f"• <b>{item}</b>: {note}", body))

    # --- DEFERRED (not machine-verified) ---
    deferred = [c for c in result.get("checks", []) if c.get("result") == "DEFERRED"]
    if deferred:
        story.append(Paragraph("Not machine-verified (DEFERRED) — manual responsibility", h2))
        for c in deferred:
            story.append(Paragraph(
                f"• <b>{c.get('check_code')}</b> {c.get('check_name')}: {c.get('reason','')}",
                body))

    # --- Quality Approval block ---
    story.append(Spacer(1, 0.25 * inch))
    story.append(Paragraph("Quality Approval (WI052 §3.7)", h2))
    story.append(Paragraph(
        f"Signed by: <b>{signer_name}</b> &nbsp;•&nbsp; Date: <b>{generated}</b>", body))
    story.append(Paragraph(
        f"Processed in {result.get('processor_ms','')} ms • "
        f"Submission {result.get('submission_id','')}", small))

    SimpleDocTemplate(out_path, pagesize=letter,
                      topMargin=0.6 * inch, bottomMargin=0.6 * inch,
                      leftMargin=0.6 * inch, rightMargin=0.6 * inch).build(story)
    return out_path
