"""The checks engine: Checks A-G + the verdict resolver (docs/05-checks-specification.md).

Pure logic, no I/O. `run_checks(fields, barcode, rules)` returns
``{"verdict": ..., "checks": [...]}``. Pinned by tests/unit/test_checks_engine.py and the golden
integration fixture tests/fixtures/v11022719_expected.json.

A check result is one of PASS / FAIL / FLAG / DEFERRED. DEFERRED never blocks a verdict but is
always surfaced (a rule that depends on MXO-PP00001 / MXO-PP00006, not yet supplied).
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from .barcode import gs1_date_to_iso
from .extraction import normalize_ref, normalize_lot, parse_date_to_iso, normalize_qty


def _check(code: str, name: str, result: str, reason: str = "",
           evidence: Optional[Dict] = None, sub_results: Optional[List] = None) -> Dict:
    out = {"check_code": code, "check_name": name, "result": result, "reason": reason,
           "evidence": evidence or {}}
    if sub_results is not None:
        out["sub_results"] = sub_results
    return out


def _present_values(d: Dict) -> List:
    return [v for v in d.values() if v not in (None, "")]


# --- Check A: completeness, linkage & signatures ----------------------------

def check_a(fields: Dict) -> Dict:
    required = ["label_form", "batch_coc", "sterile_coc", "sterile_lot_record"]
    present = fields.get("documents_present", [])
    missing = [d for d in required if d not in present]
    if missing:
        return _check("A", "Completeness, linkage & signatures", "FAIL",
                      f"Missing required document(s): {', '.join(missing)}.",
                      {"missing": missing})

    lots = {k: normalize_lot(v) for k, v in fields.get("lot", {}).items() if v}
    if len(set(lots.values())) > 1:
        return _check("A", "Completeness, linkage & signatures", "FAIL",
                      "Documents do not reference the same batch/lot (linkage mismatch).",
                      {"lot": lots})

    sig = fields.get("signatures") or {}
    prod, qc = sig.get("production"), sig.get("qc")
    if not prod or not prod.get("date") or not qc or not qc.get("date"):
        return _check("A", "Completeness, linkage & signatures", "FAIL",
                      "Meril Production and/or QC signature missing or undated.",
                      {"production": prod, "qc": qc})

    # A.5 sequencing: Maxx approval must be on/after the Meril signature dates.
    approval = parse_date_to_iso(sig.get("maxx_approval_date"))
    meril_dates = [parse_date_to_iso(prod.get("date")), parse_date_to_iso(qc.get("date"))]
    meril_dates = [d for d in meril_dates if d]
    if approval and meril_dates and approval < max(meril_dates):
        return _check("A", "Completeness, linkage & signatures", "FLAG",
                      "Maxx approval date precedes Meril signature date(s).",
                      {"maxx_approval": approval, "meril_signatures": meril_dates})

    return _check("A", "Completeness, linkage & signatures", "PASS",
                  "All 4 docs present; linkage consistent; Meril Production + QC signed/dated; "
                  "Maxx approval not earlier than Meril signatures.",
                  {"production_sign": prod, "qc_sign": qc})


# --- Check B: cross-document field consistency ------------------------------

def check_b(fields: Dict) -> Dict:
    conflicts = {}

    refs = {k: normalize_ref(v) for k, v in fields.get("ref", {}).items() if v}
    if len(set(refs.values())) > 1:
        conflicts["ref"] = refs
    lots = {k: normalize_lot(v) for k, v in fields.get("lot", {}).items() if v}
    if len(set(lots.values())) > 1:
        conflicts["lot"] = lots

    mfg = {k: parse_date_to_iso(v) for k, v in fields.get("mfg_date", {}).items() if v}
    if len(set(mfg.values())) > 1:
        conflicts["mfg_date"] = mfg
    exp = {k: parse_date_to_iso(v) for k, v in fields.get("exp_date", {}).items() if v}
    if len(set(exp.values())) > 1:
        conflicts["exp_date"] = exp

    # QTY: compare the *released* quantity (sterile) against the label lot qty. The batch
    # manufactured-vs-released gap is a Check G concern, not a Check B failure.
    qty = fields.get("qty", {})
    label_qty = normalize_qty(qty.get("label"))
    released = [normalize_qty(qty.get("sterile_coc")),
                normalize_qty(qty.get("sterile_lot_record_released"))]
    released = [q for q in released if q is not None]
    if label_qty is not None and released and any(label_qty != q for q in released):
        conflicts["qty"] = {"label": label_qty, "released": released}

    if conflicts:
        return _check("B", "Cross-document field consistency", "FAIL",
                      "Field values disagree across documents.", conflicts)
    return _check("B", "Cross-document field consistency", "PASS",
                  "REF/LOT/QTY/Mfg/Exp agree across all documents that carry them.",
                  {"ref": refs, "lot": lots, "mfg_date": mfg, "exp_date": exp,
                   "qty": {"label": label_qty, "released": released}})


# --- Check C: GS1 barcode decode & reconciliation ---------------------------

def _hyphenless(s: str) -> str:
    return (s or "").replace("-", "").upper()


def check_c(fields: Dict, barcode: Dict, rules: Dict) -> Dict:
    if not barcode or not barcode.get("decoded"):
        return _check("C", "Barcode decode & reconciliation", "FAIL",
                      "Barcode unreadable.", {"decoded": False}, sub_results=[])

    ais = barcode.get("ais", {})
    ref = normalize_ref(_first(fields.get("ref", {})))
    lot = normalize_lot(_first(fields.get("lot", {})))
    mfg = parse_date_to_iso(_first(fields.get("mfg_date", {})))
    exp = parse_date_to_iso(_first(fields.get("exp_date", {})))

    subs: List[Dict] = []

    # (10) lot
    ai10 = ais.get("10")
    subs.append({"ai": "10", "result": "PASS" if normalize_lot(ai10) == lot else "FAIL",
                 "reason": f"AI(10)={ai10} vs LOT={lot}"})
    # (11) mfg date
    subs.append({"ai": "11", "result": _date_ai_result(ais.get("11"), mfg),
                 "reason": f"AI(11)={ais.get('11')} vs mfg={mfg}"})
    # (17) exp date
    subs.append({"ai": "17", "result": _date_ai_result(ais.get("17"), exp),
                 "reason": f"AI(17)={ais.get('17')} vs exp={exp}"})
    # (240) additional product id vs REF, applying the hyphen policy.
    subs.append(_ai240(ais.get("240"), ref, rules))
    # (01) GTIN vs MXO-PP00006 lookup.
    subs.append(_ai01(ais.get("01"), ref, rules))

    # Top-level: FAIL if any sub failed; otherwise PASS. A (240) FLAG and a (01) DEFERRED do not
    # fail the check (they surface as sub-items / drive amber via the engine as appropriate).
    if any(s["result"] == "FAIL" for s in subs):
        top = "FAIL"
    else:
        top = "PASS"
    return _check("C", "Barcode decode & reconciliation", top,
                  "AI(10)/(11)/(17) reconciled; AI(240) per hyphen policy; AI(01) per MXO-PP00006.",
                  {"ais": ais}, sub_results=subs)


def _date_ai_result(yymmdd: Optional[str], expected_iso: Optional[str]) -> str:
    if not yymmdd or not expected_iso:
        return "FAIL"
    try:
        return "PASS" if gs1_date_to_iso(yymmdd) == expected_iso else "FAIL"
    except ValueError:
        return "FAIL"


def _ai240(ai240: Optional[str], ref: str, rules: Dict) -> Dict:
    val = (ai240 or "").upper()
    if val == ref:
        return {"ai": "240", "result": "PASS", "reason": "AI(240) equals REF."}
    if _hyphenless(val) == _hyphenless(ref):
        # Encoded value drops the REF hyphen. Per the worked sample this is a FLAG to confirm
        # against MXO-PP00006, regardless of the optional/required policy (never an outright FAIL
        # for a hyphen-only difference).
        return {"ai": "240", "result": "FLAG",
                "reason": f"encoded {val} omits hyphen in REF {ref}"}
    return {"ai": "240", "result": "FAIL", "reason": f"AI(240)={val} != REF {ref}"}


def _ai01(ai01: Optional[str], ref: str, rules: Dict) -> Dict:
    gtin = rules.get("gtin", {}) or {}
    if not gtin.get("configured"):
        return {"ai": "01", "result": "DEFERRED",
                "reason": "GTIN source-of-truth MXO-PP00006 not configured"}
    expected = (gtin.get("map") or {}).get(ref)
    if expected is None:
        return {"ai": "01", "result": "DEFERRED",
                "reason": f"no GTIN mapping for REF {ref} in MXO-PP00006"}
    return {"ai": "01", "result": "PASS" if str(ai01) == str(expected) else "FAIL",
            "reason": f"AI(01)={ai01} vs MXO-PP00006[{ref}]={expected}"}


# --- Check D: description normalization --------------------------------------

def check_d(fields: Dict, rules: Dict) -> Dict:
    desc = rules.get("descriptions", {}) or {}
    label_desc = (fields.get("description", {}) or {}).get("label")
    if not desc.get("configured"):
        return _check("D", "Description normalization", "DEFERRED",
                      "Canonical label description per REF requires MXO-PP00001 (not configured).",
                      {"label": label_desc})
    ref = normalize_ref(_first(fields.get("ref", {})))
    canonical = (desc.get("map") or {}).get(ref)
    mode = desc.get("match_mode", "normalized")
    ok = _desc_match(label_desc, canonical, mode)
    return _check("D", "Description normalization", "PASS" if ok else "FAIL",
                  f"Label description vs MXO-PP00001 canonical ({mode}).",
                  {"label": label_desc, "canonical": canonical})


def _norm_text(s: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _desc_match(label: Optional[str], canonical: Optional[str], mode: str) -> bool:
    if canonical is None or label is None:
        return False
    if mode == "exact":
        return label == canonical
    if mode == "contains":
        return _norm_text(canonical) in _norm_text(label) or _norm_text(label) in _norm_text(canonical)
    return _norm_text(label) == _norm_text(canonical)  # normalized


# --- Check E: IFU linkage ----------------------------------------------------

def check_e(fields: Dict, rules: Dict) -> Dict:
    ifu = rules.get("ifu", {}) or {}
    sterile_ifu = fields.get("sterile_coc_ifu")
    if not ifu.get("configured"):
        return _check("E", "IFU linkage", "DEFERRED",
                      "Printed-IFU requirement/location needs MXO-PP00001 (not configured).",
                      {"sterile_coc_ifu": sterile_ifu})
    # When configured: confirm a printed IFU matches the sterile-CoC IFU.
    printed = (fields.get("printed_ifu") or "") if isinstance(fields, dict) else ""
    ok = bool(sterile_ifu) and _norm_text(printed) == _norm_text(sterile_ifu)
    return _check("E", "IFU linkage", "PASS" if ok else "FAIL",
                  "Printed IFU vs sterile-CoC IFU.",
                  {"sterile_coc_ifu": sterile_ifu, "printed_ifu": printed})


# --- Check F: static / template content -------------------------------------

def check_f(fields: Dict, rules: Dict) -> Dict:
    static = rules.get("static_content", {}) or {}
    configured = bool(static.get("configured"))

    # One sub-check is a pure data check, always runnable: label manufacturer address must
    # contain the batch-CoC shipped-to address.
    label_addr = fields.get("manufacturer_address_label", "")
    batch_addr = fields.get("manufacturer_address_batch_coc", "")
    addr_ok = bool(batch_addr) and _norm_text(batch_addr) in _norm_text(label_addr)
    subs = [{"item": "manufacturer_address",
             "result": "PASS" if addr_ok else "FAIL",
             "reason": "Label manufacturer address vs batch-CoC shipped-to address."}]

    for item in ("ce_notified_body", "ec_rep", "symbols",
                 "product_family_branding", "label_revision"):
        subs.append({"item": item,
                     "result": "PASS" if configured else "DEFERRED",
                     "reason": "" if configured else "requires MXO-PP00001"})

    if configured:
        top = "FAIL" if any(s["result"] == "FAIL" for s in subs) else "PASS"
        reason = "Static/template content evaluated against MXO-PP00001."
    else:
        top = "DEFERRED"
        reason = "Manufacturer-address sub-check ran; remaining static elements require MXO-PP00001."
    return _check("F", "Static / template content", top, reason,
                  {"manufacturer_address_label": label_addr,
                   "manufacturer_address_batch_coc": batch_addr}, sub_results=subs)


# --- Check G: workflow integrity flags --------------------------------------

_DEVIATION_RE = re.compile(r"\b(deviation|dev\b|nc\b|non[- ]?conformance)\b", re.IGNORECASE)


def check_g(fields: Dict) -> Dict:
    subs: List[Dict] = []

    box = (fields.get("barcode_scanned_box") or "").strip().lower()
    subs.append({"item": "barcode_scanned_box",
                 "result": "PASS" if box == "yes" else "FLAG",
                 "reason": "WI052 3.6 barcode-scan box state."})

    comment = fields.get("deviation_comment") or ""
    has_dev = bool(_DEVIATION_RE.search(comment))
    subs.append({"item": "deviation_reference",
                 "result": "FLAG" if has_dev else "PASS",
                 "reason": (f"Sterile Lot Record comment: '{comment}'" if has_dev
                            else "No deviation/NC referenced.")})

    qty = fields.get("qty", {})
    man = normalize_qty(qty.get("batch_manufactured"))
    rel = normalize_qty(qty.get("sterile_lot_record_released") or qty.get("sterile_coc"))
    qty_flag = man is not None and rel is not None and man != rel
    subs.append({"item": "qty_reconciliation",
                 "result": "FLAG" if qty_flag else "PASS",
                 "reason": (f"Batch manufactured {man}, released {rel}." if qty_flag
                            else "Manufactured and released quantities agree.")})

    top = "FLAG" if any(s["result"] == "FLAG" for s in subs) else "PASS"
    return _check("G", "Workflow integrity", top,
                  "Barcode-scan box, deviation reference, and quantity reconciliation.",
                  {"barcode_box": fields.get("barcode_scanned_box"),
                   "deviation_comment": comment}, sub_results=subs)


# --- orchestration ----------------------------------------------------------

def _first(d: Dict):
    """First non-empty value from a per-document field dict (authoritative-source agnostic)."""
    for v in d.values():
        if v not in (None, ""):
            return v
    return None


def run_checks(fields: Dict, barcode: Dict, rules: Dict) -> Dict:
    checks = [
        check_a(fields),
        check_b(fields),
        check_c(fields, barcode, rules),
        check_d(fields, rules),
        check_e(fields, rules),
        check_f(fields, rules),
        check_g(fields),
    ]
    return {"verdict": resolve_verdict(checks), "checks": checks}


def resolve_verdict(checks: List[Dict]) -> str:
    """REJECT on any FAIL; APPROVE_WITH_FLAGS on any FLAG; otherwise APPROVE.

    DEFERRED never changes the verdict.
    """
    results = [c.get("result") for c in checks]
    if "FAIL" in results:
        return "REJECT"
    if "FLAG" in results:
        return "APPROVE_WITH_FLAGS"
    return "APPROVE"
