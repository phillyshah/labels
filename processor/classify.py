"""Document-type validation against the known WI052 batch-document templates.

Each required slot has a *distinctive* marker set drawn from the reference samples
(reference-documents/samples/). On upload we read the text layer of each file and check it
substantially matches the template for the slot it was dropped into — and, importantly, that it
does not match a *different* slot's template better (the common real-world error is swapping the
two Certificates of Compliance, which share the "Certificate of Compliance" heading).

The label form is image-only (no text layer), so it is matched structurally rather than by text.

`classify_documents` returns a list of human-readable issues; an empty list means everything
looks right. The pipeline turns any issues into a clear, blocking notification rather than
silently analysing the wrong document.
"""

from __future__ import annotations

from typing import Dict, List, Optional

# Distinctive markers per slot: chosen to appear in that document type and be largely absent in
# the others. Lower-cased; matched as tolerant substrings (the scanned docs carry OCR noise).
TEMPLATES: Dict[str, Dict] = {
    "label_form": {
        "name": "Reference Label form",
        "image_only": True,
        "markers": [],
    },
    "batch_coc": {
        "name": "Batch Certificate of Compliance",
        "image_only": False,
        "markers": ["certificate no", "shipped to", "quantity shipped",
                    "drawing revision", "fir report", "ref.batch", "customer po"],
    },
    "sterile_coc": {
        "name": "Sterile Certificate of Compliance",
        "image_only": False,
        "markers": ["batch/lot", "mfg. date", "exp. date", "customer p/n", "mfg date", "exp date"],
    },
    "sterile_lot_record": {
        "name": "Sterile Lot Record",
        "image_only": False,
        "markers": ["sterile lot record", "form 1023", "sterile lot number",
                    "sterilizer", "chamber", "lot number"],
    },
}

# A slot is considered a confident match for a template at >= this many distinct markers.
_MATCH_THRESHOLD = 2
# Below this much text we treat a slot as effectively image-only (a label, not a paper form).
_MIN_TEXT_CHARS = 120


def _score(text_low: str, slot: str) -> int:
    return sum(1 for m in TEMPLATES[slot]["markers"] if m in text_low)


def _best_text_match(text_low: str, exclude: Optional[str] = None):
    """(slot, score) of the best-matching text template, ignoring `exclude`."""
    best, best_score = None, 0
    for slot, tpl in TEMPLATES.items():
        if tpl["image_only"] or slot == exclude:
            continue
        s = _score(text_low, slot)
        if s > best_score:
            best, best_score = slot, s
    return best, best_score


def classify_documents(texts: Dict[str, Optional[str]]) -> List[Dict]:
    """`texts` maps slot -> extracted text-layer string (or "" / None for image-only).

    Returns a list of issue dicts: {slot, expected, looks_like, detail}.
    """
    issues: List[Dict] = []

    for slot, tpl in TEMPLATES.items():
        if slot not in texts:
            continue  # optional/absent slot — completeness is handled elsewhere
        text = (texts.get(slot) or "")
        low = text.lower()
        substantial = len(text.strip()) >= _MIN_TEXT_CHARS

        if tpl["image_only"]:
            # The label form should be image-only. If a text-heavy form was dropped here and it
            # matches a paper template, it's the wrong file.
            if substantial:
                other, other_score = _best_text_match(low)
                if other and other_score >= _MATCH_THRESHOLD:
                    issues.append(_issue(slot, looks_like=other,
                                         detail="this looks like a paper form, not the image-based label"))
            continue

        # Text-bearing slot.
        own = _score(low, slot)
        if own >= _MATCH_THRESHOLD:
            continue  # confident correct match

        other, other_score = _best_text_match(low, exclude=slot)
        if other and other_score >= _MATCH_THRESHOLD and other_score > own:
            issues.append(_issue(slot, looks_like=other))
        elif not substantial:
            issues.append(_issue(slot, looks_like=None,
                                 detail="no readable certificate text was found (is this the image-only label?)"))
        else:
            issues.append(_issue(slot, looks_like=None))
    return issues


def _issue(slot: str, looks_like: Optional[str], detail: Optional[str] = None) -> Dict:
    expected_name = TEMPLATES[slot]["name"]
    if detail is None:
        if looks_like:
            detail = f"it more closely matches a {TEMPLATES[looks_like]['name']}"
        else:
            detail = "it does not substantially match the expected template"
    return {"slot": slot, "expected": expected_name,
            "looks_like": TEMPLATES[looks_like]["name"] if looks_like else None,
            "detail": detail}


def describe(issues: List[Dict]) -> str:
    """Render issues into one user-facing notification string."""
    parts = []
    for it in issues:
        label = it["slot"].replace("_", " ")
        parts.append(f"The “{label}” slot: {it['detail']}.")
    parts.append("Please check you uploaded the right file in each slot.")
    return " ".join(parts)
