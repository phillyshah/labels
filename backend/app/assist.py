"""LLM-assist extension point (phase 2).

The training section accumulates a labeled corpus: each past batch's full processor result plus
per-check reviewer feedback (correct / partial / wrong + expected value + note). That corpus is
the input for an optional, later LLM-assisted step that proposes concrete rule/config changes
(e.g. a looser description match, a new GTIN mapping, a tightened flag) for a human to review and
apply — keeping the runtime processor deterministic and auditable.

This module is intentionally a no-op stub today: the data model and storage are in place
(`feedback` table + `submissions.result_json`), so wiring an Anthropic call here later is additive
and needs no schema change. `propose_rule_changes` returns an empty list until that phase lands.
"""

from __future__ import annotations

from typing import Dict, List


def propose_rule_changes(corpus: List[Dict]) -> List[Dict]:
    """Given the feedback corpus, return suggested rule/config edits for human review.

    Phase-1: returns []. Phase-2 will summarise where the processor disagreed with reviewers and
    draft config deltas (description maps, GTIN entries, threshold tweaks) via the Claude API.
    """
    return []
