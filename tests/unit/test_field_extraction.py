"""
Unit tests for field extraction + normalization helpers.

These focus on the deterministic normalization rules that Check B depends on, which can be
tested without PDFs. Full extraction-from-PDF is covered in the integration tier.

Import contract:
    from processor.extraction import normalize_ref, normalize_lot, parse_date_to_iso, normalize_qty
If the team names these differently, provide shims so these imports resolve.
"""

import pytest
from processor.extraction import (
    normalize_ref,
    normalize_lot,
    parse_date_to_iso,
)


# --- REF normalization ------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("MTUUX400-K", "MTUUX400-K"),
    (" mtuux400-k ", "MTUUX400-K"),
    ("MTUUX400-K\n", "MTUUX400-K"),
])
def test_normalize_ref(raw, expected):
    assert normalize_ref(raw) == expected


def test_ref_preserves_internal_hyphen():
    # The hyphen is meaningful in REF and must NOT be stripped (unlike AI 240 policy).
    assert normalize_ref("MTUUX400-K") == "MTUUX400-K"
    assert normalize_ref("MTUUX400K") != normalize_ref("MTUUX400-K")


# --- LOT normalization ------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("V11022719", "V11022719"),
    (" v11022719 ", "V11022719"),
])
def test_normalize_lot(raw, expected):
    assert normalize_lot(raw) == expected


# --- Date normalization -----------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("2026-03-01", "2026-03-01"),
    ("2031-02-28", "2031-02-28"),
    ("01-Apr-2026", "2026-04-01"),
    ("15-Apr-2026", "2026-04-15"),
])
def test_parse_date_to_iso(raw, expected):
    assert parse_date_to_iso(raw) == expected


def test_gs1_date_matches_printed_date():
    # The barcode (11)260301 and the printed 2026-03-01 must resolve equal.
    from processor.barcode import gs1_date_to_iso  # team may colocate this
    assert gs1_date_to_iso("260301") == parse_date_to_iso("2026-03-01")
