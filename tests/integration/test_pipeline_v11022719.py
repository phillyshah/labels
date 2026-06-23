"""
HEADLINE integration test.

Runs the four REAL sample PDFs through the full processor pipeline and asserts the result
matches the golden fixture (ignoring processor_ms and submission_id). If this passes, the system
reproduces the manual label review for batch V11022719 / sterile lot M26-179.

Import contract:
    from processor.pipeline import process_submission

Sample documents live at ../reference-documents/samples/ relative to the repo root.
"""

import json
import os
import pathlib
import pytest

from processor.pipeline import process_submission

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SAMPLES = REPO_ROOT / "reference-documents" / "samples"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "v11022719_expected.json"

DOCUMENTS = {
    "label_form":         str(SAMPLES / "1__V11022719_label.pdf"),
    "batch_coc":          str(SAMPLES / "1__V11022719_COC.pdf"),
    "sterile_coc":        str(SAMPLES / "M26-179_COC.pdf"),
    "sterile_lot_record": str(SAMPLES / "Sterile_Lot_Record_M26-179.pdf"),
}

UNCONFIGURED_RULES = {
    "rules_version": "2026-06-01.unconfigured",
    "gtin": {"configured": False, "ai240_hyphen": "optional", "map": {}},
    "descriptions": {"configured": False, "match_mode": "normalized", "map": {}},
    "ifu": {"configured": False, "required_on_label": True},
    "static_content": {"configured": False, "families": {}, "ref_to_family": {}},
}


@pytest.fixture(scope="module")
def result():
    for p in DOCUMENTS.values():
        assert os.path.exists(p), f"missing sample: {p}"
    return process_submission(DOCUMENTS, UNCONFIGURED_RULES)


@pytest.fixture(scope="module")
def expected():
    return json.loads(FIXTURE.read_text())


def _check(result, code):
    return next(c for c in result["checks"] if c["check_code"] == code)


def test_verdict(result, expected):
    assert result["verdict"] == expected["verdict"] == "APPROVE_WITH_FLAGS"


def test_identity_fields(result, expected):
    ident = result["identity"]
    exp = expected["identity"]
    assert ident["ref"] == exp["ref"]
    assert ident["lot"] == exp["lot"]
    assert ident["sterile_lot"] == exp["sterile_lot"]
    assert ident["qty_released"] == exp["qty_released"]
    assert ident["mfg_date"] == exp["mfg_date"]
    assert ident["exp_date"] == exp["exp_date"]


def test_barcode_ais(result, expected):
    assert result["barcode"]["decoded"] is True
    assert result["barcode"]["ais"] == expected["barcode"]["ais"]


@pytest.mark.parametrize("c,expected_result", [
    ("A", "PASS"),
    ("B", "PASS"),
    ("C", "PASS"),
    ("D", "DEFERRED"),
    ("E", "DEFERRED"),
    ("F", "DEFERRED"),
    ("G", "FLAG"),
])
def test_each_check_top_level_result(result, c, expected_result):
    assert _check(result, c)["result"] == expected_result


def test_C_sub_results(result):
    subs = {s["ai"]: s["result"] for s in _check(result, "C")["sub_results"]}
    assert subs["10"] == "PASS"
    assert subs["11"] == "PASS"
    assert subs["17"] == "PASS"
    assert subs["240"] == "FLAG"
    assert subs["01"] == "DEFERRED"


def test_F_manufacturer_address_subcheck_passes(result):
    subs = {s["item"]: s["result"] for s in _check(result, "F")["sub_results"]}
    assert subs["manufacturer_address"] == "PASS"


def test_G_sub_flags(result):
    subs = {s["item"]: s["result"] for s in _check(result, "G")["sub_results"]}
    assert subs["barcode_scanned_box"] == "FLAG"
    assert subs["deviation_reference"] == "FLAG"
    assert subs["qty_reconciliation"] == "FLAG"
