# Tests

This suite defines "done." The processor and frontend must make it pass. The tests are written
against a small **import contract** the coding team implements in the `processor` package. The
contract is intentionally minimal so the team is free in *how* they implement, but pinned in
*what* the functions return.

## Import contract (implement these in the processor)

```python
# processor/pipeline.py
def process_submission(documents: dict, rules: dict) -> dict:
    """documents: {type: local_path}. rules: parsed rules.yaml.
       Returns the result dict shaped per docs/07-api-spec.md."""

# processor/extraction.py
def extract_fields(documents: dict) -> "ExtractedFields": ...

# processor/barcode.py
def decode_label_barcodes(label_path: str) -> dict:   # {symbology, ais:{...}, decoded:bool}
def parse_gs1(payload: str) -> dict:                  # {"01":..., "10":..., ...}

# processor/checks.py
def run_checks(fields, barcode, rules) -> dict:       # {verdict, checks:[...]}
def resolve_verdict(checks: list) -> str:             # APPROVE | APPROVE_WITH_FLAGS | REJECT
```

If your implementation differs, provide thin adapter shims so these import paths resolve — the
tests import them directly.

## Layout

- `unit/` — pure logic, no I/O. Fast. Run on every PR.
- `integration/` — full pipeline against the real sample PDFs in
  `../reference-documents/samples/`, plus DB/RLS tests.
- `e2e/` — Playwright against the running UI.
- `fixtures/v11022719_expected.json` — the golden result. The anchor of the suite.

## Run

```bash
pytest tests/unit tests/integration -v
npx playwright test tests/e2e        # needs the stack up
```

## The one test that matters most

`integration/test_pipeline_v11022719.py` runs the four real sample documents end-to-end and
asserts the output equals the golden fixture (ignoring timing + ids). If that passes, the system
reproduces the manual label review for a known-good batch. Everything else guards the edges.

## Notes for the team

- Tests reference sample PDFs by relative path; keep the `reference-documents/samples/` folder
  intact next to `tests/`.
- The unit tests for checks build `ExtractedFields` by hand (no PDFs needed), so you can develop
  the checks engine before extraction is finished.
- Keep everything deterministic; see `integration/test_determinism.py`.
