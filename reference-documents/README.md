# Reference Documents

These are the authoritative source documents for the build. Do not modify them.

## Governing documents (the rules of the process)

| File | What it is | How the build uses it |
|---|---|---|
| `WI052_-_Product_Label_Approval_Procedure_R01.pdf` | The Work Instruction that defines the entire label-approval process. **Section 3.0** covers Meril labels — that is the scope of this build. | The source of the process logic. Every workflow step and check traces back to a clause here. |
| `WI052-F1_-_Label_Approval_Record_R01.pdf` | The paper "Label Approval Record" form that the current process fills out by hand. | The app replaces this form. The generated digital approval record mirrors its fields (Item #, Qty, Lot #, Description, Outer/Inner Label, Comments, Barcode Scanned & Verified, Quality Approval signature). |

## Sample batch (the worked example / test gold standard)

The `samples/` folder is one real, complete submission for a single batch. Together they are
the "happy-ish path" the integration test asserts against (it produces `APPROVE_WITH_FLAGS`
because of two real procedural anomalies — see `tests/fixtures/v11022719_expected.json`).

| File | What it is | Key fields it is the source of truth for |
|---|---|---|
| `samples/1__V11022719_label.pdf` | Meril "Reference Label 1st Copy Before Printing Lot Label" form for batch **V11022719** (Tibial Base Plate, Size 4, REF MTUUX400-K). Contains the Tray, Patient/Inner, and Outer label zones; Meril Production + QC signatures; and the Maxx Approval block. | The label content under review. Also the 2D GS1 barcode payload. |
| `samples/1__V11022719_COC.pdf` | Meril batch-level Certificate of Compliance (#2603000843) for batch V11022719. | REF / Customer P/N, batch number, batch qty (40 made / 38 shipped), description, material, drawing rev. **No expiration date** (pre-sterile). |
| `samples/M26-179_COC.pdf` | Meril sterile-lot Certificate of Compliance for sterile lot **M26-179** (bundles V11022719 with 11 other batches). | **Mfg date (2026-03-01) and Exp date (2031-02-28)**, per-batch released qty, and the applicable IFU(s): MXO-00022 Rev T (standard) and MXO-00229 Rev 01 (Infinia Femoral, asterisked items). |
| `samples/Sterile_Lot_Record_M26-179.pdf` | Maxx internal post-sterilization release record (Form 1023-2) for lot M26-179, including the Documentation Release Verification Form (W1008-F2) and Sterile Product Release Verification Form (1023-1). | Final released quantities, sterilizer (ISL), chamber (C), BI lot (BAD-026), and lot-level release signatures. **Comment notes "Released under deviation 25.17"** — the source of one of the procedural flags. |

## The data-lineage principle (read this before coding the checks)

A label is correct when its content **reconciles across this chain of documents**. No single
document is complete on its own:

- **Identity** (REF, LOT, description) appears on the label, the batch CoC, the sterile CoC,
  and the Sterile Lot Record — and they must agree.
- **Dates** (mfg, exp) exist **only** on the sterile CoC and the label. The batch CoC has none.
- **Final quantity** comes from the post-sterile released qty (sterile CoC / Sterile Lot
  Record), not the batch CoC's manufactured qty.
- **Static content** (CE mark, EC REP, manufacturer block, symbols, product-family branding,
  label revision) is governed by **MXO-PP00001**, which is not yet in this package.
- **GTIN** inside the barcode is governed by **MXO-PP00006**, also not yet supplied.

The full field-by-field mapping is in `docs/05-checks-specification.md`.
