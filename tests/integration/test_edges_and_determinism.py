"""
Integration tests for the failure/edge paths and determinism, against the real sample PDFs.

Import contract:
    from processor.pipeline import process_submission
    process_submission raises a ProcessingError (or returns an error dict) for blocking
    conditions; tests below accept either an exception with a `.code` or a result dict with
    an "error" key. Adapt the helper if your team uses a different convention.
"""

import os
import pathlib
import pytest

from processor.pipeline import process_submission

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SAMPLES = REPO_ROOT / "reference-documents" / "samples"

DOCUMENTS = {
    "label_form":         str(SAMPLES / "1__V11022719_label.pdf"),
    "batch_coc":          str(SAMPLES / "1__V11022719_COC.pdf"),
    "sterile_coc":        str(SAMPLES / "M26-179_COC.pdf"),
    "sterile_lot_record": str(SAMPLES / "Sterile_Lot_Record_M26-179.pdf"),
}

RULES = {
    "rules_version": "2026-06-01.unconfigured",
    "gtin": {"configured": False, "ai240_hyphen": "optional", "map": {}},
    "descriptions": {"configured": False, "match_mode": "normalized", "map": {}},
    "ifu": {"configured": False, "required_on_label": True},
    "static_content": {"configured": False, "families": {}, "ref_to_family": {}},
}


def _error_code(callable_):
    """Run callable_; return the error code whether raised or returned."""
    try:
        res = callable_()
    except Exception as e:  # ProcessingError expected
        return getattr(e, "code", type(e).__name__)
    if isinstance(res, dict) and res.get("error"):
        return res["error"]
    return None


def test_missing_document_is_blocked():
    docs = dict(DOCUMENTS)
    del docs["sterile_coc"]
    code = _error_code(lambda: process_submission(docs, RULES))
    assert code in ("MISSING_DOCUMENT", "ValueError", "KeyError") or code is not None


def test_linkage_mismatch_is_blocked():
    # Point the sterile-lot slot at the WRONG sterile lot record by reusing the batch CoC
    # (which does not establish the M26-179 linkage the label expects).
    docs = dict(DOCUMENTS)
    docs["sterile_lot_record"] = str(SAMPLES / "1__V11022719_COC.pdf")  # wrong doc type/linkage
    # Either classified as wrong type (MISSING/UNCLASSIFIED) or as a linkage mismatch.
    code = _error_code(lambda: process_submission(docs, RULES))
    assert code is not None


def test_determinism_same_input_same_output():
    r1 = process_submission(DOCUMENTS, RULES)
    r2 = process_submission(DOCUMENTS, RULES)
    r3 = process_submission(DOCUMENTS, RULES)

    def strip(r):
        r = dict(r)
        r.pop("processor_ms", None)
        r.pop("submission_id", None)
        return r

    assert strip(r1) == strip(r2) == strip(r3)


@pytest.mark.skipif(not all(os.path.exists(p) for p in DOCUMENTS.values()),
                    reason="sample PDFs not present")
def test_runs_within_time_budget():
    import time
    t0 = time.time()
    process_submission(DOCUMENTS, RULES)
    assert time.time() - t0 < 30, "submission must process in under 30s on target hardware"
