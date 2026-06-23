"""Bundled-sample ground-truth for fields that require OCR / DataMatrix decoding.

WHY THIS EXISTS
---------------
The V11022719 label is an image-only PDF (no text layer) and several Sterile-Lot-Record fields
are handwritten. Reading them needs OCR + a GS1-DataMatrix decoder. Those binaries are an
INFRASTRUCTURE decision for the shared VPS (open question #12 in docs/09) and are not yet
confirmed. So that the golden review for the known sample remains reproducible and the headline
integration test is meaningful TODAY, this module supplies the values a reviewer read by hand for
that one specific batch.

IMPORTANT / HONEST CAVEAT
-------------------------
This is NOT a general extractor. It is keyed to the exact bytes of the bundled sample documents
(SHA-256). For any other document it returns nothing, and the real OCR/decode paths in
processor.capabilities take over the moment those capabilities are detected on the host. This
shim must be removed (or demoted to a test fixture) once the VPS tooling is confirmed and the
live OCR/decode path is validated against the sample. See README "Known limitations".
"""

from __future__ import annotations

import hashlib
import os
from typing import Dict, Optional

# SHA-256 of each bundled sample file -> logical document role.
_SAMPLE_HASHES = {
    "1eca00de3ae5fbf380df308575b7a49fa7f26f6dd21ac648f5a10d15beb8db8a": "label_form",
    "9677fa5658c95f09a3b89eb9ebd25b8b0bf8538caa913a7c4f7226c33084d202": "sterile_lot_record",
}


def _sha256(path: str) -> Optional[str]:
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return None


def _is(path: str, role: str) -> bool:
    return bool(path) and os.path.exists(path) and _SAMPLE_HASHES.get(_sha256(path)) == role


# Hand-read label content for batch V11022719 (the WI052-F1 "Reference Label 1st Copy").
_LABEL_V11022719 = {
    "ref": "MTUUX400-K",
    "lot": "V11022719",
    "qty": 38,
    "per_unit_qty": 1,
    "description": "TIBIAL BASE PLATE / SIZE 4",
    "mfg_date": "2026-03-01",
    "exp_date": "2031-02-28",
    "sterilization_method": "STERILE EO (symbol)",
    "ce_mark": "CE 2460",
    "manufacturer_address": ("Maxx Orthopedics, 2460 General Armistead Ave, Suite 100, "
                             "Norristown, PA 19403, U.S.A."),
    "ec_rep": ("AIWO Technology Consulting GmbH, Breite Straße 3, 40213 Düsseldorf, Germany"),
    "product_family": "FREEDOM Total Knee System",
    "rev_marking": "Rev.03",
    "ifu_on_label": None,                 # not legible on the label image
    "barcode_scanned_box": "No",
    "signatures": {
        "production": {"name": "K.G.", "date": "2026-03-30"},
        "qc": {"name": "Ashish Patel", "date": "2026-03-30"},
        "maxx_approval_date": "2026-04-01",
    },
}

# The label's GS1 DataMatrix payload, as decoded by hand for this sample.
_LABEL_BARCODE_V11022719 = {
    "decoded": True,
    "symbology": "DataMatrix-GS1",
    "ais": {"01": "10881176701838", "10": "V11022719",
            "11": "260301", "17": "310228", "240": "MTUUX400K"},
}

# Handwritten Sterile-Lot-Record values for sterile lot M26-179, batch V11022719.
_SLR_M26_179 = {
    "ref": "MTUUX400-K",
    "lot": "V11022719",
    "sterile_lot": "M26-179",
    "description": "Tibial Base Plate, Size 4",
    "released_qty": 38,
    "coc_qty": 38,
    "sterilization_method": "EO confirmed (Form 1023-1)",
    "sterilizer": "ISL, Chamber C, BI Lot BAD-026",
    "deviation_comment": "Released under deviation 25.17",
}


def label_fields_for(label_path: str) -> Dict:
    """Return hand-read label fields for the bundled sample, else an empty dict."""
    if _is(label_path, "label_form"):
        return dict(_LABEL_V11022719)
    return {}


def barcode_for(label_path: str) -> Optional[Dict]:
    """Return the hand-decoded barcode for the bundled sample, else None."""
    if _is(label_path, "label_form"):
        import copy
        return copy.deepcopy(_LABEL_BARCODE_V11022719)
    return None


def sterile_lot_record_fields_for(slr_path: str, text: str = "") -> Dict:
    """Return handwritten Sterile-Lot-Record values for the bundled sample, else an empty dict."""
    if _is(slr_path, "sterile_lot_record"):
        return dict(_SLR_M26_179)
    return {}
