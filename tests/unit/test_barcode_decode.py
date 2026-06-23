"""
Unit tests for GS1 Application Identifier parsing.

Import contract:
    from processor.barcode import parse_gs1

parse_gs1 takes the decoded DataMatrix payload string and returns a dict of AI -> value.
The V11022719 label encodes:
    (01)10881176701838(10)V11022719(11)260301(17)310228(240)MTUUX400K
"""

import pytest
from processor.barcode import parse_gs1


SAMPLE_PAYLOAD = "(01)10881176701838(10)V11022719(11)260301(17)310228(240)MTUUX400K"
# Many scanners emit FNC1-delimited payloads without parentheses; support both.
SAMPLE_PAYLOAD_FNC1 = "\x1d011088117670183810V11022719\x1d11260301\x1d17310228\x1d240MTUUX400K"


def test_parses_all_ais_parenthesized():
    ais = parse_gs1(SAMPLE_PAYLOAD)
    assert ais["01"] == "10881176701838"
    assert ais["10"] == "V11022719"
    assert ais["11"] == "260301"
    assert ais["17"] == "310228"
    assert ais["240"] == "MTUUX400K"


def test_parses_fnc1_form():
    ais = parse_gs1(SAMPLE_PAYLOAD_FNC1)
    assert ais["01"] == "10881176701838"
    assert ais["10"] == "V11022719"
    assert ais["240"] == "MTUUX400K"


def test_fixed_length_ais_consume_correct_width():
    # (01) is fixed 14 digits, (11)/(17) fixed 6. A run-on must still split correctly.
    ais = parse_gs1(SAMPLE_PAYLOAD)
    assert len(ais["01"]) == 14
    assert len(ais["11"]) == 6
    assert len(ais["17"]) == 6


def test_date_ai_interpretation_helpers_optional():
    # If the team exposes a helper to turn YYMMDD into ISO, it must match. Skip if absent.
    barcode = pytest.importorskip("processor.barcode")
    if hasattr(barcode, "gs1_date_to_iso"):
        assert barcode.gs1_date_to_iso("260301") == "2026-03-01"
        assert barcode.gs1_date_to_iso("310228") == "2031-02-28"


def test_malformed_payload_does_not_crash():
    # Garbage in -> empty/partial dict, never an exception.
    ais = parse_gs1("not a gs1 payload")
    assert isinstance(ais, dict)


def test_empty_payload_returns_empty_dict():
    assert parse_gs1("") == {}
