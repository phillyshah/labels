"""AI-assisted rule-tuning suggestions from the training feedback corpus.

The training section accumulates a labeled corpus: each past batch's full processor result plus
per-check reviewer feedback (correct / partial / wrong + expected value + note). Where the tool
disagreed with a reviewer, that is a signal the rules/heuristics could be tuned.

`propose_rule_changes` sends the *disagreements* (plus the current rule config) to the Claude API
and asks for concrete, reviewable change proposals — entries for the description/GTIN maps, a
threshold tweak, an extraction fix. It NEVER applies anything: the runtime processor stays
deterministic and auditable, and a human applies whichever suggestions they accept.

Safe by default: with no ANTHROPIC_API_KEY (or the SDK absent), it returns a clear "not enabled"
message instead of failing. Nothing here runs during normal label processing.
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

_DEFAULT_MODEL = "claude-sonnet-4-6"

_SYSTEM = (
    "You are a quality engineer tuning a deterministic, rule-based medical-device label checker "
    "(checks A–G against config in rules.yaml). You are given (1) the current tunable rule config "
    "and (2) cases where a human reviewer disagreed with the tool's output. Propose concrete, "
    "minimal, auditable changes to the rules/heuristics that would resolve the disagreements "
    "WITHOUT masking real defects. Never invent values not supported by the feedback. Prefer "
    "config-map entries (descriptions, gtin) and explicit threshold changes. If a disagreement is "
    "the reviewer's error or needs data not present, say so instead of inventing a change.\n\n"
    "Return ONLY JSON: {\"suggestions\":[{\"title\":str,\"target\":str,\"rationale\":str,"
    "\"proposed_change\":str,\"confidence\":\"low\"|\"medium\"|\"high\"}]}. `target` names the rule "
    "area (e.g. 'rules.descriptions.map', 'rules.gtin.map', 'check C / AI(240)', "
    "'extraction.signatures'). `proposed_change` is a short, copy-pasteable description or YAML snippet."
)


def propose_rule_changes(corpus: List[Dict], current_rules: Optional[Dict] = None) -> Dict:
    """Return {available, message, suggestions[]}.

    `corpus` is the list of disagreement rows from the store (rating != 'correct').
    """
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return {"available": False, "suggestions": [],
                "message": "AI suggestions are off. Set ANTHROPIC_API_KEY in the deployment to enable."}
    if not corpus:
        return {"available": True, "suggestions": [],
                "message": "No reviewer disagreements yet — rate some training batches first."}

    try:
        from anthropic import Anthropic
    except Exception:
        return {"available": False, "suggestions": [],
                "message": "The anthropic package is not installed in this build."}

    rules_excerpt = _rules_excerpt(current_rules or {})
    user = (
        "CURRENT RULE CONFIG (tunable parts):\n"
        + json.dumps(rules_excerpt, indent=2)
        + "\n\nREVIEWER DISAGREEMENTS (tool output vs. what the reviewer said):\n"
        + json.dumps(corpus[:200], indent=2, default=str)
        + "\n\nPropose rule/heuristic changes as specified."
    )
    try:
        client = Anthropic(api_key=key)
        resp = client.messages.create(
            model=os.environ.get("ASSIST_MODEL", _DEFAULT_MODEL),
            max_tokens=2000,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        suggestions = _parse(text)
        msg = (f"{len(suggestions)} suggestion(s) drafted from "
               f"{len(corpus)} disagreement(s). Review and apply manually.")
        return {"available": True, "suggestions": suggestions, "message": msg}
    except Exception as e:  # network / auth / parse
        return {"available": False, "suggestions": [],
                "message": f"AI suggestion call failed: {type(e).__name__}: {str(e)[:160]}"}


def _rules_excerpt(rules: Dict) -> Dict:
    """Only the parts a suggestion can sensibly touch."""
    keep = ("rules_version", "gtin", "descriptions", "ifu", "static_content")
    return {k: rules.get(k) for k in keep if k in rules}


def _parse(text: str) -> List[Dict]:
    """Best-effort JSON extraction from the model reply."""
    text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return []
    try:
        data = json.loads(text[start:end + 1])
    except Exception:
        return []
    out = []
    for s in data.get("suggestions", []):
        if isinstance(s, dict) and s.get("title"):
            out.append({
                "title": str(s.get("title", "")),
                "target": str(s.get("target", "")),
                "rationale": str(s.get("rationale", "")),
                "proposed_change": str(s.get("proposed_change", "")),
                "confidence": str(s.get("confidence", "")),
            })
    return out
