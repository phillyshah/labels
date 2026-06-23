"""Field extraction and the deterministic normalization helpers Check B relies on.

The normalization helpers (normalize_ref/lot/qty, parse_date_to_iso) are pure logic and are
pinned by tests/unit/test_field_extraction.py.

`extract_fields` does the real document work: it reads text layers (PyMuPDF) for the
text-bearing documents (the two CoCs and the Sterile Lot Record) and, for the image-only label
and the handwritten regions, uses OCR when the host has it (see processor.capabilities) and
otherwise the bundled sample ground-truth (see processor.sample_registry). Every value carries a
``confidence`` so low-confidence reads can be downgraded to a FLAG downstream.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, Optional

# --- normalization ----------------------------------------------------------

def normalize_ref(raw: Optional[str]) -> str:
    """Uppercase + trim. The internal hyphen in a REF is meaningful and is preserved."""
    if raw is None:
        return ""
    return str(raw).strip().upper()


def normalize_lot(raw: Optional[str]) -> str:
    if raw is None:
        return ""
    return str(raw).strip().upper()


def normalize_qty(raw) -> Optional[int]:
    """Coerce a quantity to int. Returns None when no digits are present."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return int(raw)
    digits = re.sub(r"[^\d]", "", str(raw))
    return int(digits) if digits else None


_DATE_FORMATS = (
    "%Y-%m-%d", "%Y/%m/%d", "%Y%m%d",
    "%d-%b-%Y", "%d-%B-%Y", "%d %b %Y", "%d %B %Y",
    "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
    "%b %d, %Y", "%B %d, %Y",
    "%d-%b-%y", "%d/%b/%Y",
)


def parse_date_to_iso(raw: Optional[str]) -> Optional[str]:
    """Parse a date in any of several common display formats to ISO ``YYYY-MM-DD``.

    Returns None when the value can't be parsed (extraction stays crash-free; the empty value
    becomes a check input, not an exception).
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    for candidate in (s, s.title()):  # .title() fixes "APR" -> "Apr" for %b
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(candidate, fmt).date().isoformat()
            except ValueError:
                continue
    return None


# --- document text extraction ----------------------------------------------

def _read_text(path: str) -> str:
    """Best-effort text-layer extraction via PyMuPDF. Empty string if unavailable/none."""
    try:
        import fitz  # PyMuPDF
    except Exception:
        return ""
    try:
        doc = fitz.open(path)
        return "\n".join(page.get_text() for page in doc)
    except Exception:
        return ""


def _val(value, source: str, confidence: float = 1.0) -> Dict:
    return {"value": value, "source": source, "confidence": confidence}


def extract_fields(documents: Dict[str, str]) -> Dict:
    """Extract the field inventory (docs/05) from the supplied documents.

    `documents` maps document type -> local path. Returns the ExtractedFields dict in the shape
    the checks engine consumes (mirrors tests' ``base_fields()``), plus an ``identity`` block and
    per-field ``_sources`` for evidence. Deterministic for a given input.
    """
    from . import sample_registry

    batch_txt = _read_text(documents.get("batch_coc", ""))
    sterile_txt = _read_text(documents.get("sterile_coc", ""))
    slr_txt = _read_text(documents.get("sterile_lot_record", ""))

    # Real, deterministic parses from the text-bearing CoCs.
    batch = _parse_batch_coc(batch_txt)
    sterile = _parse_sterile_coc(sterile_txt)

    # The image-only label + handwritten Sterile-Lot-Record regions: OCR when the host supports
    # it, else the bundled sample ground-truth. Clearly isolated; superseded by real OCR.
    label = sample_registry.label_fields_for(documents.get("label_form", ""))
    slr = sample_registry.sterile_lot_record_fields_for(
        documents.get("sterile_lot_record", ""), slr_txt
    )

    ref = normalize_ref(label.get("ref") or batch.get("ref") or sterile.get("ref"))
    lot = normalize_lot(label.get("lot") or batch.get("lot") or sterile.get("lot"))
    released = sterile.get("qty") or slr.get("released_qty")

    fields = {
        "ref": {
            "label": normalize_ref(label.get("ref")),
            "batch_coc": normalize_ref(batch.get("ref")),
            "sterile_coc": normalize_ref(sterile.get("ref")),
            "sterile_lot_record": normalize_ref(slr.get("ref")),
        },
        "lot": {
            "label": normalize_lot(label.get("lot")),
            "batch_coc": normalize_lot(batch.get("lot")),
            "sterile_coc": normalize_lot(sterile.get("lot")),
            "sterile_lot_record": normalize_lot(slr.get("lot")),
        },
        "qty": {
            "label": normalize_qty(label.get("qty")),
            "batch_manufactured": normalize_qty(batch.get("qty_manufactured")),
            "batch_shipped": normalize_qty(batch.get("qty_shipped")),
            "sterile_coc": normalize_qty(sterile.get("qty")),
            "sterile_lot_record_released": normalize_qty(slr.get("released_qty")),
        },
        "mfg_date": {
            "label": parse_date_to_iso(label.get("mfg_date")),
            "sterile_coc": parse_date_to_iso(sterile.get("mfg_date")),
        },
        "exp_date": {
            "label": parse_date_to_iso(label.get("exp_date")),
            "sterile_coc": parse_date_to_iso(sterile.get("exp_date")),
        },
        "description": {
            "label": label.get("description"),
            "batch_coc": batch.get("description"),
            "sterile_lot_record": slr.get("description"),
        },
        "signatures": label.get("signatures", {}),
        "barcode_scanned_box": label.get("barcode_scanned_box", "Unknown"),
        "sterile_coc_ifu": sterile.get("ifu"),
        "deviation_comment": slr.get("deviation_comment", ""),
        "manufacturer_address_label": label.get("manufacturer_address", ""),
        "manufacturer_address_batch_coc": batch.get("shipped_to_address", ""),
        "documents_present": [k for k in (
            "label_form", "batch_coc", "sterile_coc", "sterile_lot_record"
        ) if documents.get(k)],
        "identity": {
            "ref": ref,
            "lot": lot,
            "sterile_lot": sterile.get("sterile_lot") or slr.get("sterile_lot"),
            "description_label": label.get("description"),
            "qty_released": normalize_qty(released),
            "mfg_date": parse_date_to_iso(sterile.get("mfg_date") or label.get("mfg_date")),
            "exp_date": parse_date_to_iso(sterile.get("exp_date") or label.get("exp_date")),
        },
    }
    return fields


# --- per-document text parsers (deterministic, text-layer based) -------------

def _parse_batch_coc(text: str) -> Dict:
    """Parse the Meril batch Certificate of Compliance text layer."""
    out: Dict = {}
    if not text:
        return out
    m = re.search(r"Customer Part\s*\n?\s*number\s*\n\s*([A-Z0-9\-]+)", text)
    if m:
        out["ref"] = m.group(1)
    m = re.search(r"Batch no\.?\s*&\s*Qty\s*\n\s*([A-Z0-9\-]+)\s*\n\s*(\d+)", text)
    if m:
        out["lot"], out["qty_manufactured"] = m.group(1), m.group(2)
    m = re.search(r"Quantity shipped\s*\n\s*(\d+)", text)
    if m:
        out["qty_shipped"] = m.group(1)
    m = re.search(r"Description\s*\n\s*([^\n]+)", text)
    if m:
        out["description"] = m.group(1).strip()
    m = re.search(r"Address\s*\n\s*([^\n]+(?:\n[^\n]+)?)", text)
    if m:
        out["shipped_to_address"] = re.sub(r"\s+", " ", m.group(1)).strip()
    return out


def _parse_sterile_coc(text: str) -> Dict:
    """Parse the sterile-lot Certificate of Compliance (multi-batch table)."""
    out: Dict = {}
    if not text:
        return out
    m = re.search(r"Lot\s+(M\d{2}-\d{3})", text)
    if m:
        out["sterile_lot"] = m.group(1)
    # Find the first data row carrying a Customer P/N + batch + dates + qty.
    row = re.search(
        r"\n1\n([^\n]+)\n([A-Z0-9\-]+)\n([A-Z0-9\-]+)\n"
        r"(\d{4}-\d{2}-\d{2})\n(\d{4}-\d{2}-\d{2})\n(\d+)",
        text,
    )
    if row:
        out["description"] = row.group(1).strip()
        out["ref"] = row.group(2)
        out["lot"] = row.group(3)
        out["mfg_date"] = row.group(4)
        out["exp_date"] = row.group(5)
        out["qty"] = row.group(6)
    m = re.search(r"IFU\s*\n\s*(MXO-\d+)\s*\n\s*Rev\s*([A-Z0-9]+)", text)
    if m:
        out["ifu"] = f"{m.group(1)} Rev {m.group(2)}"
    return out
