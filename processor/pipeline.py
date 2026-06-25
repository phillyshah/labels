"""End-to-end processing pipeline: documents -> extracted fields -> barcode -> checks -> result.

`process_submission(documents, rules)` is the import-contract entrypoint the integration tests
target. It is deterministic (same input + rules => same output, excluding processor_ms).

Blocking conditions (missing document, wrong document type, linkage mismatch) are returned as an
error dict (the tests accept either an error dict with an ``error`` key or a raised exception).
"""

from __future__ import annotations

import time
from typing import Dict, Optional

from . import capabilities
from .barcode import decode_label_barcodes
from .checks import run_checks
from .extraction import extract_fields, normalize_lot
from .report import build_source_of_truth

REQUIRED_DOCS = ("label_form", "batch_coc", "sterile_coc", "sterile_lot_record")


class ProcessingError(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _error(code: str, detail: str, submission_id: Optional[str]) -> Dict:
    return {"error": code, "detail": detail, "submission_id": submission_id}


def process_submission(documents: Dict[str, str], rules: Dict,
                       submission_id: Optional[str] = None) -> Dict:
    t0 = time.time()
    rules = rules or {}

    # Stage 1a -- completeness.
    missing = [d for d in REQUIRED_DOCS if not documents.get(d)]
    if missing:
        return _error("MISSING_DOCUMENT", f"{missing[0]} not provided", submission_id)

    # Stage 1b -- document identification (template match). A file dropped into the wrong slot
    # (e.g. the two Certificates of Compliance swapped, or a CoC where the label belongs) is
    # caught here and surfaced as a clear notification rather than analysed silently.
    classification_error = _classify(documents)
    if classification_error:
        return _error(*classification_error, submission_id=submission_id)

    # Stage 2 -- field extraction (text layers + OCR/sample for image-only regions).
    fields = extract_fields(documents)

    # Stage 1c -- linkage: the label LOT must agree across the documents.
    lots = {k: normalize_lot(v) for k, v in fields.get("lot", {}).items() if v}
    if len(set(lots.values())) > 1:
        return _error("LINKAGE_MISMATCH",
                      f"label LOT not consistent across documents: {lots}", submission_id)

    # Stage 3 -- barcode decode.
    barcode = decode_label_barcodes(documents["label_form"])

    # Stage 4 -- checks engine.
    engine = run_checks(fields, barcode, rules)

    # Stage 5 -- assemble the API-shaped result (docs/07) + the Section-1 source-of-truth table.
    identity = fields.get("identity", {})
    result = {
        "submission_id": submission_id,
        "verdict": engine["verdict"],
        "rules_version": rules.get("rules_version"),
        "processor_ms": int((time.time() - t0) * 1000),
        "identity": identity,
        "barcode": barcode,
        "source_of_truth": build_source_of_truth(fields, barcode),
        "checks": engine["checks"],
    }
    return result


def _classify(documents: Dict[str, str]) -> Optional[tuple]:
    """Verify each supplied file matches the document type of its slot, against the known
    WI052 templates. Returns an (error_code, detail) tuple on a confident mismatch, else None.
    """
    from .classify import classify_documents, describe
    from .extraction import _read_text  # local import: text-layer probe

    texts = {slot: _read_text(path) for slot, path in documents.items()
             if path and slot in {"label_form", "batch_coc", "sterile_coc", "sterile_lot_record"}}
    issues = classify_documents(texts)
    if issues:
        return ("DOCUMENT_MISMATCH", describe(issues))
    return None
