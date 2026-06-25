"""
Unit tests for the checks engine (Checks A-G + verdict resolver).

These build ExtractedFields by hand so they run with no PDFs and no network -- the team can
develop the engine against these before extraction is wired up.

Import contract (see tests/README.md):
    from processor.checks import run_checks, resolve_verdict

The fixtures below mirror the V11022719 sample but are hand-authored so each check can be
exercised in isolation, including the negative cases the sample doesn't show.
"""

import copy
import pytest

from processor.checks import run_checks, resolve_verdict  # implemented by the coding team


# --- helpers ----------------------------------------------------------------

def base_fields():
    """A clean, internally-consistent V11022719-like field set."""
    return {
        "ref": {"label": "MTUUX400-K", "batch_coc": "MTUUX400-K",
                "sterile_coc": "MTUUX400-K", "sterile_lot_record": "MTUUX400-K"},
        "lot": {"label": "V11022719", "batch_coc": "V11022719",
                "sterile_coc": "V11022719", "sterile_lot_record": "V11022719"},
        "qty": {"label": 38, "batch_manufactured": 40, "batch_shipped": 38,
                "sterile_coc": 38, "sterile_lot_record_released": 38},
        "mfg_date": {"label": "2026-03-01", "sterile_coc": "2026-03-01"},
        "exp_date": {"label": "2031-02-28", "sterile_coc": "2031-02-28"},
        "description": {"label": "TIBIAL BASE PLATE / SIZE 4",
                        "batch_coc": "TIBIAL BASE 4 METALBACKED",
                        "sterile_lot_record": "Tibial Base Plate, Size 4"},
        "signatures": {"production": {"name": "K.G.", "date": "2026-03-30"},
                       "qc": {"name": "Ashish Patel", "date": "2026-03-30"},
                       "maxx_approval_date": "2026-04-01"},
        "barcode_scanned_box": "No",
        "sterile_coc_ifu": "MXO-00022 Rev T",
        "deviation_comment": "Released under deviation 25.17",
        "manufacturer_address_label": "Maxx Orthopedics, 2460 General Armistead Ave, Suite 100, Norristown, PA 19403, U.S.A.",
        "manufacturer_address_batch_coc": "2460 General Armistead Ave, Suite 100, Norristown, PA 19403",
        "documents_present": ["label_form", "batch_coc", "sterile_coc", "sterile_lot_record"],
    }


def base_barcode():
    return {
        "decoded": True,
        "symbology": "DataMatrix-GS1",
        "ais": {"01": "10881176701838", "10": "V11022719",
                "11": "260301", "17": "310228", "240": "MTUUX400K"},
    }


def unconfigured_rules():
    return {
        "rules_version": "test.unconfigured",
        "gtin": {"configured": False, "ai240_hyphen": "optional", "map": {}},
        "descriptions": {"configured": False, "match_mode": "normalized", "map": {}},
        "ifu": {"configured": False, "required_on_label": True},
        "static_content": {"configured": False, "families": {}, "ref_to_family": {}},
    }


def code(result, c):
    return next(x for x in result["checks"] if x["check_code"] == c)


# --- Check A ----------------------------------------------------------------

def test_A_pass_when_complete_linked_and_signed():
    r = run_checks(base_fields(), base_barcode(), unconfigured_rules())
    assert code(r, "A")["result"] == "PASS"


def test_A_fail_when_document_missing():
    f = base_fields()
    f["documents_present"].remove("sterile_coc")
    r = run_checks(f, base_barcode(), unconfigured_rules())
    assert code(r, "A")["result"] == "FAIL"


def test_A_fail_when_linkage_mismatch():
    f = base_fields()
    f["lot"]["sterile_coc"] = "V99999999"  # label lot not in sterile lot
    r = run_checks(f, base_barcode(), unconfigured_rules())
    assert code(r, "A")["result"] == "FAIL"


def test_A_fail_when_meril_signature_missing():
    f = base_fields()
    f["signatures"]["qc"] = None
    r = run_checks(f, base_barcode(), unconfigured_rules())
    assert code(r, "A")["result"] == "FAIL"


def test_A_flag_when_approval_predates_meril_signatures():
    f = base_fields()
    f["signatures"]["maxx_approval_date"] = "2026-03-29"  # before Meril signed
    r = run_checks(f, base_barcode(), unconfigured_rules())
    assert code(r, "A")["result"] in ("FLAG", "FAIL")


# --- Check B ----------------------------------------------------------------

def test_B_pass_on_consistent_fields():
    r = run_checks(base_fields(), base_barcode(), unconfigured_rules())
    assert code(r, "B")["result"] == "PASS"


def test_B_fail_when_ref_differs():
    f = base_fields()
    f["ref"]["sterile_coc"] = "MTUUX200-K"
    r = run_checks(f, base_barcode(), unconfigured_rules())
    assert code(r, "B")["result"] == "FAIL"


def test_B_fail_when_exp_date_differs():
    f = base_fields()
    f["exp_date"]["label"] = "2030-02-28"
    r = run_checks(f, base_barcode(), unconfigured_rules())
    assert code(r, "B")["result"] == "FAIL"


def test_B_passes_despite_manufactured_vs_released_qty_gap():
    # 40 manufactured vs 38 released is a Check G concern, NOT a Check B failure.
    f = base_fields()
    assert f["qty"]["batch_manufactured"] != f["qty"]["sterile_lot_record_released"]
    r = run_checks(f, base_barcode(), unconfigured_rules())
    assert code(r, "B")["result"] == "PASS"


def test_B_fail_when_label_qty_differs_from_released():
    f = base_fields()
    f["qty"]["label"] = 37
    r = run_checks(f, base_barcode(), unconfigured_rules())
    assert code(r, "B")["result"] == "FAIL"


# --- Check C ----------------------------------------------------------------

def test_C_core_ais_pass():
    r = run_checks(base_fields(), base_barcode(), unconfigured_rules())
    c = code(r, "C")
    subs = {s["ai"]: s["result"] for s in c["sub_results"]}
    assert subs["10"] == "PASS" and subs["11"] == "PASS" and subs["17"] == "PASS"


def test_C_ai240_flag_when_hyphen_required():
    rules = unconfigured_rules()
    rules["gtin"]["ai240_hyphen"] = "required"
    r = run_checks(base_fields(), base_barcode(), rules)
    subs = {s["ai"]: s["result"] for s in code(r, "C")["sub_results"]}
    assert subs["240"] in ("FLAG", "FAIL")


def test_C_ai240_pass_when_hyphen_optional():
    rules = unconfigured_rules()
    rules["gtin"]["ai240_hyphen"] = "optional"
    r = run_checks(base_fields(), base_barcode(), rules)
    subs = {s["ai"]: s["result"] for s in code(r, "C")["sub_results"]}
    # default sample behavior treats the dropped hyphen as a FLAG even when optional-for-PASS;
    # accept either PASS or FLAG depending on the team's chosen default, but never FAIL.
    assert subs["240"] in ("PASS", "FLAG")


def test_C_gtin_deferred_when_mxopp00006_absent():
    r = run_checks(base_fields(), base_barcode(), unconfigured_rules())
    subs = {s["ai"]: s["result"] for s in code(r, "C")["sub_results"]}
    assert subs["01"] == "DEFERRED"


def test_C_gtin_pass_when_configured_and_matching():
    rules = unconfigured_rules()
    rules["gtin"] = {"configured": True, "ai240_hyphen": "optional",
                     "map": {"MTUUX400-K": "10881176701838"}}
    r = run_checks(base_fields(), base_barcode(), rules)
    subs = {s["ai"]: s["result"] for s in code(r, "C")["sub_results"]}
    assert subs["01"] == "PASS"


def test_C_gtin_fail_when_configured_and_mismatch():
    rules = unconfigured_rules()
    rules["gtin"] = {"configured": True, "ai240_hyphen": "optional",
                     "map": {"MTUUX400-K": "00000000000000"}}
    r = run_checks(base_fields(), base_barcode(), rules)
    subs = {s["ai"]: s["result"] for s in code(r, "C")["sub_results"]}
    assert subs["01"] == "FAIL"


def test_C_fail_when_barcode_unreadable():
    bc = {"decoded": False, "symbology": None, "ais": {}}
    r = run_checks(base_fields(), bc, unconfigured_rules())
    assert code(r, "C")["result"] == "FAIL"


# --- Checks D / E / F (rule-dependent) --------------------------------------

def test_D_deferred_without_rules():
    r = run_checks(base_fields(), base_barcode(), unconfigured_rules())
    assert code(r, "D")["result"] == "DEFERRED"


def test_D_pass_when_canonical_matches():
    rules = unconfigured_rules()
    rules["descriptions"] = {"configured": True, "match_mode": "exact",
                             "map": {"MTUUX400-K": "TIBIAL BASE PLATE / SIZE 4"}}
    r = run_checks(base_fields(), base_barcode(), rules)
    assert code(r, "D")["result"] == "PASS"


def test_D_fail_when_canonical_mismatch():
    rules = unconfigured_rules()
    rules["descriptions"] = {"configured": True, "match_mode": "exact",
                             "map": {"MTUUX400-K": "SOMETHING ELSE"}}
    r = run_checks(base_fields(), base_barcode(), rules)
    assert code(r, "D")["result"] == "FAIL"


def test_E_deferred_without_rules():
    r = run_checks(base_fields(), base_barcode(), unconfigured_rules())
    assert code(r, "E")["result"] == "DEFERRED"


def test_F_manufacturer_address_subcheck_passes_without_rules():
    r = run_checks(base_fields(), base_barcode(), unconfigured_rules())
    subs = {s["item"]: s["result"] for s in code(r, "F")["sub_results"]}
    assert subs["manufacturer_address"] == "PASS"
    assert subs["ce_notified_body"] == "DEFERRED"


# --- Check G ----------------------------------------------------------------

def test_G_flags_barcode_box_no():
    r = run_checks(base_fields(), base_barcode(), unconfigured_rules())
    subs = {s["item"]: s["result"] for s in code(r, "G")["sub_results"]}
    assert subs["barcode_scanned_box"] == "FLAG"


def test_G_flags_deviation_reference():
    r = run_checks(base_fields(), base_barcode(), unconfigured_rules())
    subs = {s["item"]: s["result"] for s in code(r, "G")["sub_results"]}
    assert subs["deviation_reference"] == "FLAG"


def test_G_no_deviation_flag_when_comment_clean():
    f = base_fields()
    f["deviation_comment"] = ""
    r = run_checks(f, base_barcode(), unconfigured_rules())
    subs = {s["item"]: s["result"] for s in code(r, "G")["sub_results"]}
    assert subs["deviation_reference"] == "PASS"


def test_G_barcode_box_pass_when_yes():
    f = base_fields()
    f["barcode_scanned_box"] = "Yes"
    r = run_checks(f, base_barcode(), unconfigured_rules())
    subs = {s["item"]: s["result"] for s in code(r, "G")["sub_results"]}
    assert subs["barcode_scanned_box"] == "PASS"


# --- Verdict resolver -------------------------------------------------------

def test_verdict_reject_on_any_fail():
    checks = [{"check_code": "B", "result": "FAIL"}, {"check_code": "A", "result": "PASS"}]
    assert resolve_verdict(checks) == "REJECT"


def test_verdict_amber_on_flag_no_fail():
    checks = [{"check_code": "G", "result": "FLAG"}, {"check_code": "B", "result": "PASS"}]
    assert resolve_verdict(checks) == "APPROVE_WITH_FLAGS"


def test_verdict_approve_when_all_pass_or_deferred():
    checks = [{"check_code": "B", "result": "PASS"}, {"check_code": "D", "result": "DEFERRED"}]
    assert resolve_verdict(checks) == "APPROVE"


def test_deferred_never_blocks():
    checks = [{"check_code": "D", "result": "DEFERRED"},
              {"check_code": "E", "result": "DEFERRED"}]
    assert resolve_verdict(checks) == "APPROVE"


# --- Whole-sample verdict ---------------------------------------------------

def test_full_sample_resolves_to_amber():
    r = run_checks(base_fields(), base_barcode(), unconfigured_rules())
    assert r["verdict"] == "APPROVE_WITH_FLAGS"
