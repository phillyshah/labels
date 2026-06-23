# 07 — API Specification

Contract between `web` and `processor`, plus the data shapes the test suite asserts against.
All processor endpoints require the `X-Processor-Secret: <PROCESSOR_SHARED_SECRET>` header.

## `GET /healthz` (processor)

```json
200 OK
{
  "status": "ok",
  "capabilities": {
    "pdf_text": "pdftotext",          // or "pdfplumber" / "pymupdf" / null
    "pdf_raster": "pdftoppm",
    "ocr": "tesseract",
    "barcode": "zxing-cpp",           // or "pyzbar+libdmtx" / "dmtxread" / null
    "image": "opencv"
  },
  "rules_version": "2026-06-01.unconfigured"
}
```
If any required capability is `null`, return `503` so deploy smoke tests fail loudly.

## `POST /process` (processor)

Request:
```json
{
  "submission_id": "uuid",
  "rules_version": "2026-06-01.unconfigured",
  "documents": {
    "label_form":          { "url": "https://signed-url..." },
    "batch_coc":           { "url": "https://signed-url..." },
    "sterile_coc":         { "url": "https://signed-url..." },
    "sterile_lot_record":  { "url": "https://signed-url..." },
    "doc_release_verification":            { "url": "..." },   // optional
    "sterile_product_release_verification":{ "url": "..." }    // optional
  }
}
```

Response (the canonical result shape — `tests/fixtures/v11022719_expected.json` matches this):
```json
{
  "submission_id": "uuid",
  "verdict": "APPROVE_WITH_FLAGS",
  "rules_version": "2026-06-01.unconfigured",
  "processor_ms": 4120,
  "identity": {
    "ref": "MTUUX400-K",
    "lot": "V11022719",
    "sterile_lot": "M26-179",
    "description_label": "TIBIAL BASE PLATE / SIZE 4",
    "qty_released": 38,
    "mfg_date": "2026-03-01",
    "exp_date": "2031-02-28"
  },
  "barcode": {
    "decoded": true,
    "symbology": "DataMatrix-GS1",
    "ais": {
      "01": "10881176701838",
      "10": "V11022719",
      "11": "260301",
      "17": "310228",
      "240": "MTUUX400K"
    }
  },
  "checks": [
    {
      "check_code": "A",
      "check_name": "Completeness, linkage & signatures",
      "result": "PASS",
      "reason": "All 4 docs present; linkage consistent; Meril Production + QC signed/dated; Maxx approval date not earlier than Meril signatures.",
      "evidence": {
        "production_sign": { "value": "K.G. 2026-03-30", "source": "label_form#p1" },
        "qc_sign":         { "value": "Ashish Patel 2026-03-30", "source": "label_form#p1" }
      }
    },
    {
      "check_code": "B",
      "check_name": "Cross-document field consistency",
      "result": "PASS",
      "reason": "REF/LOT/QTY/Mfg/Exp agree across all documents that carry them.",
      "evidence": {
        "ref":     { "label": "MTUUX400-K", "batch_coc": "MTUUX400-K", "sterile_coc": "MTUUX400-K", "sterile_lot_record": "MTUUX400-K" },
        "lot":     { "label": "V11022719", "batch_coc": "V11022719", "sterile_coc": "V11022719", "sterile_lot_record": "V11022719" },
        "qty":     { "label": 38, "sterile_coc": 38, "sterile_lot_record": 38 },
        "mfg_date":{ "label": "2026-03-01", "sterile_coc": "2026-03-01" },
        "exp_date":{ "label": "2031-02-28", "sterile_coc": "2031-02-28" }
      }
    },
    {
      "check_code": "C",
      "check_name": "Barcode decode & reconciliation",
      "result": "PASS",
      "reason": "AI(10)/(11)/(17) match printed + source values. AI(240) omits hyphen -> flag. AI(01) GTIN not verifiable -> deferred (MXO-PP00006 not configured).",
      "sub_results": [
        { "ai": "10",  "result": "PASS" },
        { "ai": "11",  "result": "PASS" },
        { "ai": "17",  "result": "PASS" },
        { "ai": "240", "result": "FLAG", "reason": "encoded MTUUX400K omits hyphen in REF MTUUX400-K" },
        { "ai": "01",  "result": "DEFERRED", "reason": "GTIN source-of-truth MXO-PP00006 not configured" }
      ],
      "evidence": {
        "ai10": { "value": "V11022719", "matches": "label LOT + all CoCs" },
        "ai11": { "value": "260301", "matches": "2026-03-01" },
        "ai17": { "value": "310228", "matches": "2031-02-28" }
      }
    },
    {
      "check_code": "D",
      "check_name": "Description normalization",
      "result": "DEFERRED",
      "reason": "Canonical label description per REF requires MXO-PP00001 (not configured).",
      "evidence": {
        "label": "TIBIAL BASE PLATE / SIZE 4",
        "batch_coc": "TIBIAL BASE 4 METALBACKED",
        "sterile_lot_record": "Tibial Base Plate, Size 4"
      }
    },
    {
      "check_code": "E",
      "check_name": "IFU linkage",
      "result": "DEFERRED",
      "reason": "Sterile CoC assigns IFU MXO-00022 Rev T to this REF; printed-IFU requirement/location needs MXO-PP00001.",
      "evidence": { "sterile_coc_ifu": "MXO-00022 Rev T" }
    },
    {
      "check_code": "F",
      "check_name": "Static / template content",
      "result": "DEFERRED",
      "reason": "Manufacturer-address sub-check PASS; remaining static elements require MXO-PP00001.",
      "sub_results": [
        { "item": "manufacturer_address", "result": "PASS",
          "reason": "Label Maxx address matches batch CoC shipped-to address." },
        { "item": "ce_notified_body", "result": "DEFERRED" },
        { "item": "ec_rep", "result": "DEFERRED" },
        { "item": "symbols", "result": "DEFERRED" },
        { "item": "product_family_branding", "result": "DEFERRED" },
        { "item": "label_revision", "result": "DEFERRED" }
      ]
    },
    {
      "check_code": "G",
      "check_name": "Workflow integrity",
      "result": "FLAG",
      "reason": "Barcode-scan box marked No; lot released under deviation 25.17; batch qty 40 -> released 38.",
      "sub_results": [
        { "item": "barcode_scanned_box", "result": "FLAG", "reason": "Maxx Approval 'Barcode scanned & Verified' = No, contradicts WI052 3.6" },
        { "item": "deviation_reference", "result": "FLAG", "reason": "Sterile Lot Record comment: 'Released under deviation 25.17'" },
        { "item": "qty_reconciliation", "result": "FLAG", "reason": "Batch CoC manufactured 40, released 38; reduction unexplained in provided docs" }
      ],
      "evidence": {
        "barcode_box": { "value": "No", "source": "label_form#maxx_approval" },
        "deviation":   { "value": "25.17", "source": "sterile_lot_record#comments" },
        "qty":         { "manufactured": 40, "shipped": 38, "released": 38 }
      }
    }
  ]
}
```

Error response:
```json
422 Unprocessable
{ "error": "MISSING_DOCUMENT", "detail": "sterile_coc not provided", "submission_id": "uuid" }
```
```json
409 Conflict
{ "error": "LINKAGE_MISMATCH",
  "detail": "label LOT V11022719 not found in sterile CoC batch list for M26-180",
  "submission_id": "uuid" }
```

## `web` → Supabase

Standard Supabase client calls (auth, storage upload/sign, table insert/select) — no custom
REST layer needed beyond what Supabase provides. The only bespoke server call from `web` is to
the processor's `/process`.

## Versioning

`rules_version` is echoed end-to-end and persisted on the submission, so a verdict can always be
reproduced against the exact rule set that produced it.
