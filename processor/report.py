"""Report shaping: the Section-1 "source-of-truth values" table.

Mirrors the worked-example output format (Label / Batch CoC / Sterile CoC / Sterile Lot Record,
one column per document, one row per field). This is the evidence table a reviewer reads and the
table rendered into the generated approval record (the WI052-F1-equivalent). Pure logic; the
caller attaches the result under ``result["source_of_truth"]``.
"""

from __future__ import annotations

from typing import Dict, List, Optional

# Order + display labels match the worked example's Section-1 table.
_NA = "n/a"
_DASH = "—"


def _q(v) -> str:
    return "" if v is None else str(v)


def _barcode_string(barcode: Dict) -> str:
    ais = (barcode or {}).get("ais") or {}
    if not ais:
        return _NA
    order = ["01", "10", "11", "17", "240"]
    parts = [f"({ai}){ais[ai]}" for ai in order if ai in ais]
    parts += [f"({ai}){val}" for ai, val in ais.items() if ai not in order]
    return " ".join(parts)


def _row(field: str, label="", batch_coc="", sterile_coc="", sterile_lot_record="") -> Dict:
    return {"field": field, "label": _q(label), "batch_coc": _q(batch_coc),
            "sterile_coc": _q(sterile_coc), "sterile_lot_record": _q(sterile_lot_record)}


def build_source_of_truth(fields: Dict, barcode: Dict) -> List[Dict]:
    docs = fields.get("_docs", {})
    label = docs.get("label", {})
    batch = docs.get("batch", {})
    sterile = docs.get("sterile", {})
    slr = docs.get("slr", {})
    ref = fields.get("ref", {})
    lot = fields.get("lot", {})

    qty_label = label.get("qty")
    per_unit = label.get("per_unit_qty")
    qty_label_disp = _q(qty_label)
    if per_unit is not None:
        qty_label_disp = f"{qty_label} (lot QTY); {per_unit} (per-unit on outer label)"
    batch_qty_disp = _NA
    if batch.get("qty_manufactured") or batch.get("qty_shipped"):
        batch_qty_disp = f"{_q(batch.get('qty_manufactured'))} batch / {_q(batch.get('qty_shipped'))} shipped"
    slr_qty_disp = _NA
    if slr.get("coc_qty") or slr.get("released_qty"):
        slr_qty_disp = f"{_q(slr.get('coc_qty'))} (COC QTY) / {_q(slr.get('released_qty'))} (Released QTY)"

    return [
        _row("REF / Part #", ref.get("label"), ref.get("batch_coc"),
             ref.get("sterile_coc"), ref.get("sterile_lot_record")),
        _row("LOT / Batch #", lot.get("label"), lot.get("batch_coc"),
             lot.get("sterile_coc"), lot.get("sterile_lot_record")),
        _row("Description (verbatim)", label.get("description"), batch.get("description"),
             sterile.get("description"), slr.get("description")),
        _row("Quantity", qty_label_disp, batch_qty_disp, sterile.get("qty"), slr_qty_disp),
        _row("Mfg date", label.get("mfg_date"), "not stated",
             sterile.get("mfg_date"), "not stated"),
        _row("Exp date", label.get("exp_date"), "not stated",
             sterile.get("exp_date"), "not stated"),
        _row("Sterilization method", label.get("sterilization_method"), "n/a (pre-sterile)",
             "implied by lot", slr.get("sterilization_method")),
        _row("Sterilizer", "n/a on label", _NA, _NA, slr.get("sterilizer")),
        _row("IFU", label.get("ifu_on_label") or "not visible on label image",
             _NA, sterile.get("ifu"), _NA),
        _row("CE mark", label.get("ce_mark"), _NA, _NA, _NA),
        _row("Manufacturer / Distributor", label.get("manufacturer_address"),
             "Maxx Orthopedics, same address" if batch.get("shipped_to_address") else _NA, _NA, _NA),
        _row("EC REP", label.get("ec_rep"), _NA, _NA, _NA),
        _row("Product family branding", label.get("product_family"), _NA, _NA, _NA),
        _row("GS1 2D barcode (decoded)", _barcode_string(barcode), _NA, _NA, _NA),
        _row("Rev marking", label.get("rev_marking"),
             (f"Drawing Rev {batch.get('drawing_revision')} (different field)"
              if batch.get("drawing_revision") else _NA), _NA, _NA),
    ]
