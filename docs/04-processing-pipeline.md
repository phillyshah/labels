# 04 — Processing Pipeline

This is the `processor` service. It turns raw uploaded PDFs into a structured set of extracted
fields, decodes the barcode, and hands those to the checks engine (`docs/05`).

## Tooling — REUSE WHAT THE VPS ALREADY HAS

**Per the project owner: for PDF / Word / image / barcode processing, use whatever is already
installed on the VPS for other projects. Do not install a parallel stack.**

On first deploy, the processor must **detect** the available tooling and bind to it, failing
loudly at `GET /healthz` if a required capability is missing. Detect, in order of preference,
whatever is present:

| Capability | Likely already on the VPS | Detection |
|---|---|---|
| PDF text extraction | `pdftotext` (poppler), `pdfplumber`, `PyMuPDF/fitz` | check binaries on PATH / import libs |
| PDF → image raster | `pdftoppm` (poppler), `pdf2image`, `PyMuPDF` | `which pdftoppm`, import test |
| OCR (scanned/handwritten regions) | `tesseract` | `which tesseract` |
| Barcode / DataMatrix decode | `zxing`/`zxing-cpp`, `pyzbar` (+ `libdmtx` for DataMatrix), `dmtxread` | import / `which dmtxread` |
| Image preprocessing | `opencv`/`PIL` | import test |
| Word (future-proofing) | `python-docx`, `libreoffice` headless | import / `which libreoffice` |

Write a small `capabilities.py` that probes each and exposes the result on `/healthz`. The rest
of the pipeline calls capability-named wrappers (`extract_text()`, `rasterize()`,
`decode_barcodes()`) so the concrete backend is swappable. **Do not hard-code one library** —
bind to whatever the probe found.

> If a required capability is genuinely absent on the VPS, stop and tell Maxx — adding it is an
> infra decision, not something to silently `apt install` into a shared box.

## Pipeline stages

Each stage returns structured data and never throws for "expected" problems (missing field,
unreadable region) — those become check inputs, not crashes. Only infrastructure failures throw.

### Stage 1 — Document identification & linkage validation
- Classify each uploaded file: `label_form`, `batch_coc`, `sterile_coc`, `sterile_lot_record`
  (and optional release-verification forms). Classify by template fingerprint: header text,
  form numbers (`WI052-F1`, `Form 1023-2`, `Certificate of Compliance`, etc.), and layout.
- Confirm all four required types are present. If not → hard stop, verdict cannot be computed,
  return an `error` with which type is missing.
- **Linkage check (must pass before any content check runs):**
  - LOT on the label == batch number on the batch CoC.
  - That batch number appears in the sterile CoC's batch list.
  - Sterile CoC lot number == Sterile Lot Record sterile-lot number.
  - If linkage fails → the documents don't belong together → hard stop with a clear message
    ("Submitted documents do not reference the same batch/lot"). This is its own check (Check A
    linkage) and is a `FAIL`, not a crash.

### Stage 2 — Field extraction
Extract, per document, the fields enumerated in `docs/05` §"Field inventory". Produce an
internal `ExtractedFields` object shaped like the worked-example table. For each extracted
value, record **where it came from** (document type + page + region/label) so evidence can cite
it. Text regions use text extraction; stamped/handwritten regions (signatures, checkboxes,
handwritten comments like "Released under deviation 25.17") use OCR + heuristic detection and
are flagged lower-confidence.

Checkbox/signature detection needed for Check G:
- "Checked By Production" signed + dated (label form).
- "Verified By QC" signed + dated (label form).
- "Maxx Approval" block state.
- "Barcode scanned & Verified" → Yes / No (the V11022719 sample is **No**).
- Free-text comment scan on the Sterile Lot Record for deviation references
  (regex for `deviation`, `dev`, `NC`, numbers like `25.17`).

### Stage 3 — Barcode decode
- Rasterize the label's outer-label region and decode all 1D and 2D symbols.
- For GS1 DataMatrix, parse Application Identifiers. Expected AIs for this product family:
  - `(01)` GTIN-14, `(10)` lot/batch, `(11)` mfg date YYMMDD, `(17)` exp date YYMMDD,
    `(240)` additional product id.
- Return each AI's raw value + interpreted value. Do not judge here — Stage in `docs/05` Check C
  does the matching.
- If no barcode can be decoded at all, that is a `FAIL` on Check C with reason "barcode
  unreadable", not a crash.

### Stage 4 — Hand off to checks engine
Pass `ExtractedFields` + decoded barcode + the active rule set to the engine in `docs/05`. The
engine returns a list of `CheckResult` and an overall `verdict`.

### Stage 5 — Persist & respond
- Write `check_results` rows and update the `submissions` row (verdict, duration,
  rules_version) via the service-role client.
- Write `evidence.json` to storage.
- Return the structured response in `docs/07` to `web`.

## Determinism & confidence

- The pipeline must be **deterministic** for a given input + rule version (same input → same
  verdict). No randomness, no time-dependent logic except recording timestamps.
- Every extracted value carries a `confidence` (1.0 for clean text extraction, lower for OCR).
  Low-confidence values that feed a check downgrade that check's result to `FLAG` with reason
  "value read with low confidence — verify manually" rather than silently passing/failing.

## Performance target

A four-document submission should process in **well under 30 seconds** on the VPS. Rasterize
only the regions needed (don't OCR whole documents when a targeted crop suffices). Cache nothing
across requests (stateless).
