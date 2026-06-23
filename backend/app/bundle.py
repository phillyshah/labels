"""Approval-bundle / discrepancy-report PDF generation (the DHR artifact, docs/06).

Minimal but real: renders the verdict, identity, full scorecard, acknowledged flags, and the
signer of record. Styling is intentionally plain for V1 (mirrors WI052-F1 content, not its exact
layout). Degrades to None if reportlab is unavailable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional


def generate_bundle(out_path: str, result: Dict, decision: str, signer_name: str,
                    acknowledged_flags: Optional[List] = None) -> Optional[str]:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.pdfgen import canvas
    except Exception:
        return None

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(out_path, pagesize=letter)
    width, height = letter
    y = height - inch

    ident = result.get("identity", {})
    title = "LABEL APPROVAL RECORD" if decision == "RELEASED" else "LABEL DISCREPANCY REPORT"

    c.setFont("Helvetica-Bold", 16); c.drawString(inch, y, title); y -= 0.4 * inch
    c.setFont("Helvetica", 10)
    c.drawString(inch, y, f"Verdict: {result.get('verdict')}    Decision: {decision}"); y -= 0.25 * inch
    c.drawString(inch, y, f"REF {ident.get('ref')}  ·  LOT {ident.get('lot')}  ·  "
                          f"Sterile lot {ident.get('sterile_lot')}"); y -= 0.25 * inch
    c.drawString(inch, y, f"Qty released {ident.get('qty_released')}  ·  "
                          f"Mfg {ident.get('mfg_date')}  ·  Exp {ident.get('exp_date')}")
    y -= 0.4 * inch

    c.setFont("Helvetica-Bold", 12); c.drawString(inch, y, "Scorecard"); y -= 0.28 * inch
    c.setFont("Helvetica", 9)
    for chk in result.get("checks", []):
        c.drawString(inch, y, f"{chk['check_code']}  {chk['check_name']}: {chk['result']}")
        y -= 0.2 * inch
        reason = (chk.get("reason") or "")[:110]
        if reason:
            c.setFont("Helvetica-Oblique", 8); c.drawString(1.3 * inch, y, reason)
            c.setFont("Helvetica", 9); y -= 0.2 * inch
        if y < 1.5 * inch:
            c.showPage(); y = height - inch; c.setFont("Helvetica", 9)

    if acknowledged_flags:
        y -= 0.2 * inch; c.setFont("Helvetica-Bold", 11)
        c.drawString(inch, y, "Acknowledged flags"); y -= 0.24 * inch; c.setFont("Helvetica", 9)
        for f in acknowledged_flags:
            c.drawString(1.2 * inch, y, f"• {f.get('item', f)}: {f.get('note', '')}"[:110])
            y -= 0.18 * inch

    y -= 0.3 * inch; c.setFont("Helvetica-Bold", 11)
    c.drawString(inch, y, "Quality Approval (WI052 3.7)"); y -= 0.24 * inch
    c.setFont("Helvetica", 10)
    c.drawString(inch, y, f"Signed by: {signer_name}")
    c.save()
    return out_path
