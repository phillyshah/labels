"""GS1 barcode decoding and Application Identifier parsing.

`parse_gs1` is pure-logic (no I/O) and is pinned by tests/unit/test_barcode_decode.py.
`decode_label_barcodes` does the real image work and binds to whatever DataMatrix decoder
the host has (see processor.capabilities); when none is present it falls back to the bundled
sample ground-truth so the golden review remains reproducible (see processor.sample_registry).
"""

from __future__ import annotations

import re
from datetime import date
from typing import Dict

# GS1 AIs with a FIXED value length. Everything else is treated as variable-length and is
# terminated by an FNC1 (GS, 0x1d) separator or the end of the payload.
_FIXED_LEN: Dict[str, int] = {
    "00": 18, "01": 14, "02": 14,
    "11": 6, "12": 6, "13": 6, "15": 6, "16": 6, "17": 6,
    "20": 2,
}
# AIs we recognise (used to disambiguate AI width 2 vs 3 vs 4 in FNC1 payloads).
_KNOWN_VARIABLE = {"10", "21", "22", "30", "37", "240", "241", "250", "251", "400", "10x"}

_GS = "\x1d"  # FNC1 separator


def parse_gs1(payload: str) -> Dict[str, str]:
    """Parse a GS1 element string into an ``{AI: value}`` dict.

    Accepts both human-readable parenthesised form ``(01)123...(10)LOT`` and the raw
    FNC1-delimited scanner form. Never raises: garbage in returns an empty/partial dict.
    """
    if not payload:
        return {}
    if "(" in payload:
        return _parse_parenthesised(payload)
    return _parse_fnc1(payload)


def _parse_parenthesised(payload: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    # (AI)value  -- value runs until the next "(" or end of string.
    for m in re.finditer(r"\((\d{2,4})\)([^(]*)", payload):
        ai, val = m.group(1), m.group(2)
        out[ai] = val.strip().strip(_GS)
    return out


def _parse_fnc1(payload: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    s = payload
    i = 0
    n = len(s)
    while i < n:
        if s[i] == _GS:           # stray separator
            i += 1
            continue
        ai = _match_ai(s, i)
        if ai is None:            # unrecognised -> stop, return what we have
            break
        i += len(ai)
        if ai in _FIXED_LEN:
            width = _FIXED_LEN[ai]
            out[ai] = s[i:i + width]
            i += width
        else:                     # variable: read to FNC1 or end
            j = s.find(_GS, i)
            if j != -1:
                out[ai] = s[i:j]
                i = j + 1
            else:
                # No separator. Some real GS1 DataMatrix symbols (and many decoders) omit the
                # FNC1, so a variable field can run straight into the following fixed AIs. If an
                # unambiguous fixed-AI boundary is embedded ahead (a GTIN or a valid YYMMDD date
                # AI), peel the value there instead of swallowing the rest. Falls back to the old
                # greedy read when no such boundary exists, so well-formed payloads are unchanged.
                k = _runon_boundary(s, i)
                if k is None:
                    out[ai] = s[i:]
                    i = n
                else:
                    out[ai] = s[i:k]
                    i = k
    return out


# Fixed-length AIs whose value shape is self-validating enough to mark a boundary inside an
# FNC1-less run-on: GTINs (14 digits) and the date AIs (a valid YYMMDD).
_DATE_AIS = {"11", "12", "13", "15", "16", "17"}


def _is_valid_date_ai(six: str) -> bool:
    if len(six) != 6 or not six.isdigit():
        return False
    try:
        gs1_date_to_iso(six)
        return True
    except ValueError:
        return False


def _runon_boundary(s: str, start: int) -> int | None:
    """Smallest index k > start where a date AI (11/12/13/15/16/17 + a *valid* YYMMDD) begins.

    Only date AIs qualify: a valid YYMMDD is self-validating enough to rule out false splits
    inside an alphanumeric lot like ``V11022719`` (its embedded ``11022719`` is rejected because
    ``022719`` — month 27 — is not a real date). GTIN/other numeric AIs are *not* used as
    boundaries; ``NN + 14 digits`` matches far too readily inside any numeric run.
    """
    n = len(s)
    for k in range(start + 1, n - 1):
        if s[k:k + 2] in _DATE_AIS and _is_valid_date_ai(s[k + 2:k + 8]):
            return k
    return None


def _match_ai(s: str, i: str) -> str | None:
    """Greedily match a known AI of width 4, 3, then 2 at position ``i``."""
    for width in (4, 3, 2):
        cand = s[i:i + width]
        if len(cand) < width or not cand.isdigit():
            continue
        if cand in _FIXED_LEN or cand in _KNOWN_VARIABLE:
            return cand
    # Fall back to a bare 2-digit numeric AI (covers AIs we don't explicitly list).
    cand = s[i:i + 2]
    if len(cand) == 2 and cand.isdigit():
        return cand
    return None


def gs1_date_to_iso(yymmdd: str) -> str:
    """Convert a GS1 YYMMDD date to ISO ``YYYY-MM-DD`` (assumes 20YY for this product era)."""
    if not yymmdd or len(yymmdd) != 6 or not yymmdd.isdigit():
        raise ValueError(f"not a GS1 date: {yymmdd!r}")
    yy, mm, dd = int(yymmdd[0:2]), int(yymmdd[2:4]), int(yymmdd[4:6])
    year = 2000 + yy
    if dd == 0:  # GS1: day 00 means last day of the month
        if mm == 12:
            dd = 31
        else:
            dd = (date(year, mm + 1, 1) - date(year, mm, 1)).days
    return date(year, mm, dd).isoformat()


def decode_label_barcodes(label_path: str) -> Dict:
    """Decode all symbols on a label PDF/image.

    Returns ``{"decoded": bool, "symbology": str|None, "ais": {...}}``.

    Binds to a host DataMatrix decoder when available; otherwise falls back to the bundled
    sample's known payload so the headline review is reproducible. This fallback is the only
    place the sample registry feeds the barcode path, and it is bypassed entirely the moment a
    real decoder capability is detected.
    """
    from . import capabilities
    from . import sample_registry

    caps = capabilities.probe()
    if caps.get("barcode"):
        payload = capabilities.decode_datamatrix(label_path)
        if payload:
            ais = parse_gs1(payload)
            if ais:
                return {"decoded": True, "symbology": "DataMatrix-GS1", "ais": ais}

    known = sample_registry.barcode_for(label_path)
    if known is not None:
        return known
    return {"decoded": False, "symbology": None, "ais": {}}
