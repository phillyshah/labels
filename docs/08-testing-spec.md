# 08 — Testing Specification

The build is "done" when this suite passes. Tests are organized in three tiers under `tests/`.
The golden fixture `tests/fixtures/v11022719_expected.json` encodes the expected result for the
real sample batch and is the anchor of the whole suite.

## Tiers

### Unit (`tests/unit/`) — Python, pytest
Fast, no network, no Supabase. Test the pure functions of the processor.

- `test_field_extraction.py` — given a known document (the samples), extraction returns the
  expected field values with sources. Includes date-format normalization and description capture.
- `test_barcode_decode.py` — given the label's encoded payload, the GS1 AI parser returns the
  expected AI map and interpreted values; malformed payloads degrade gracefully.
- `test_checks_engine.py` — given hand-constructed `ExtractedFields` inputs, each check A–G
  returns the correct `result`. This is where you test the *logic* in isolation:
  - B fails when REF differs across documents.
  - B passes when only batch-vs-released qty differs (that's a G concern, not B).
  - C flags the AI(240) hyphen case; C defers AI(01) when MXO-PP00006 absent.
  - D/E/F defer when MXO-PP00001 absent; D/E/F evaluate when a rule set is supplied.
  - G flags the barcode-box-No, deviation-reference, and qty-reduction cases.
  - Verdict resolver: FAIL→REJECT, FLAG→APPROVE_WITH_FLAGS, clean→APPROVE, DEFERRED never
    blocks.

### Integration (`tests/integration/`) — Python, pytest
The full processor pipeline against the real sample PDFs, plus DB/RLS behavior.

- `test_pipeline_v11022719.py` — run the **actual** four sample PDFs through the whole pipeline
  and assert the result equals `fixtures/v11022719_expected.json` (modulo `processor_ms` and
  ids). **This is the headline test.** It proves the system reproduces the manual review we did
  by hand.
- `test_linkage_mismatch.py` — swap in a mismatched sterile CoC; assert `409 LINKAGE_MISMATCH`.
- `test_missing_document.py` — omit the sterile CoC; assert `422 MISSING_DOCUMENT`.
- `test_rls.py` — reviewer A cannot read reviewer B's submission (Supabase RLS). Uses a test
  Supabase project / local supabase.

### E2E (`tests/e2e/`) — Playwright (TypeScript)
Drive the deployed UI.

- `test_submission_flow.spec.ts` — log in, upload the four samples, click Go, wait for the
  scorecard, assert the amber `APPROVE_WITH_FLAGS` banner, acknowledge both flags, click
  Sign & Release, assert a bundle is produced and a history row appears.

## Running

```bash
# unit + integration (processor)
cd processor && pip install -r requirements-dev.txt   # reuse VPS libs where present
pytest ../tests/unit ../tests/integration -v

# e2e (requires the stack running locally or a staging deploy)
cd web && npx playwright test ../tests/e2e
```

## What the headline integration test pins (must not regress)

From `fixtures/v11022719_expected.json`:
- `verdict == "APPROVE_WITH_FLAGS"`
- Check A PASS, B PASS, C PASS (with the (240) flag + (01) deferred), D/E/F DEFERRED
  (F manufacturer-address sub-check PASS), G FLAG (3 sub-flags).
- identity block exactly as extracted (REF, LOT, sterile lot, qty 38, mfg 2026-03-01,
  exp 2031-02-28).
- barcode AIs exactly `{01,10,11,17,240}` with the listed values.

## When MXO-PP00001 / MXO-PP00006 arrive

Add fixtures `v11022719_expected_with_rules.json` where D/E/F and the GTIN sub-check resolve to
PASS/FAIL instead of DEFERRED, and parametrize `test_pipeline_v11022719.py` over
{no-rules, with-rules}. The no-rules fixture must continue to pass unchanged — proving the
config-driven design works.

## Determinism test

Run the pipeline on the same input 3× and assert identical output (excluding timing/ids). Guards
against accidental nondeterminism in OCR ordering or dict iteration.

## CI

Wire unit + integration into CI on every PR. E2E runs against staging on merge to main. Block
merge if the headline integration test fails.
