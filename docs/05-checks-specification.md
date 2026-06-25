# 05 — Checks Specification (the core)

This is the heart of the system. The checks engine takes the extracted fields + decoded barcode
+ active rule set and produces a list of `CheckResult` objects and one overall `verdict`.

Every `CheckResult` has: `check_code`, `check_name`, `result` (`PASS`/`FAIL`/`FLAG`/`DEFERRED`),
`reason` (one line), and `evidence` (the values compared, each tagged with its source document).

The check codes A–G map directly to the manual review process we reverse-engineered from
WI052 §3.0 and validated against the V11022719 sample.

---

## Field inventory (what to extract from where)

| Field | Label | Batch CoC | Sterile CoC | Sterile Lot Record | Authoritative source |
|---|---|---|---|---|---|
| REF / Part # | ✓ | ✓ (Customer P/N) | ✓ (Customer P/N) | ✓ (Part Number) | all must agree |
| LOT / Batch # | ✓ | ✓ (Batch no.) | ✓ (Batch/Lot #) | ✓ (Lot #) | all must agree |
| Description | ✓ | ✓ | ✓ | ✓ | canonical = MXO-PP00001 |
| Quantity | ✓ (lot qty) | made/shipped | ✓ (released) | ✓ (Released QTY) | sterile (released) qty |
| Mfg date | ✓ | — | ✓ | — | sterile CoC |
| Exp date | ✓ | — | ✓ | — | sterile CoC |
| Sterilization method | ✓ (symbol) | — | (implied) | ✓ (EO confirmed) | sterile lot record |
| IFU reference | (if printed) | — | ✓ | — | sterile CoC + MXO-PP00001 |
| GTIN (in barcode) | ✓ (AI 01) | — | — | — | MXO-PP00006 |
| CE / notified body | ✓ | — | — | — | MXO-PP00001 |
| Manufacturer block | ✓ | (shipped-to) | — | — | MXO-PP00001 |
| EC REP block | ✓ | — | — | — | MXO-PP00001 |
| Product-family branding | ✓ | — | — | — | MXO-PP00001 |
| Label revision | ✓ | (drawing rev — different) | — | — | MXO-PP00001 |

---

## Check A — Document completeness, linkage & signature sequencing

**Source:** WI052 §3.1–3.3 (Meril Production + QC sign before sending), §3.8.

A.1 All four required documents present. (Missing → `FAIL`, halt.)
A.2 Linkage: LOT ↔ batch CoC ↔ sterile CoC batch list ↔ Sterile Lot Record lot. (Mismatch →
`FAIL`, halt — wrong documents grouped.)
A.3 Meril "Checked By Production" present, signed, dated. (Missing → `FAIL`.)
A.4 Meril "Verified By QC" present, signed, dated. (Missing → `FAIL`.)
A.5 Sequencing: if a Maxx Approval date is present on the form, it is **on or after** the Meril
signature dates. (Out of order → `FLAG`.)

*V11022719 expected:* PASS. Production K.G. 30/03/2026, QC Ashish Patel 30/03/2026, Maxx
Approval 01/APR/2026 — in order.

## Check B — Cross-document field consistency

**Source:** WI052 §3.5 ("compare to Production Procedures … all necessary and correct
information"). This is the pure data-reconciliation check, no external rules needed.

For each of {REF, LOT, QTY, Mfg date, Exp date}, compare across all documents that carry it:
- All present copies equal (after normalization, see below) → `PASS`.
- Any disagreement → `FAIL`, with the conflicting values + their sources in evidence.

Normalization rules (deterministic):
- REF: uppercase, trim, preserve internal hyphen (`MTUUX400-K`). Match exactly after that.
- LOT: uppercase, trim. Match exactly.
- QTY: compare the **released** quantity (sterile CoC / Sterile Lot Record) against the label
  lot qty. The batch CoC's *manufactured* qty may differ from shipped/released — that is
  expected and handled in Check G, not a Check B failure. Released-vs-label mismatch → `FAIL`.
- Dates: parse to ISO `YYYY-MM-DD`; the label and sterile CoC must resolve to the same calendar
  date regardless of display format.

*V11022719 expected:* PASS. REF/LOT/QTY(38)/Mfg(2026-03-01)/Exp(2031-02-28) all agree.

## Check C — GS1 barcode decode & reconciliation

**Source:** WI052 §3.6 (Maxx scans QR/barcode to verify encoded info).

For the decoded DataMatrix AIs:
- `(10)` lot == printed LOT and == Check B LOT → else `FAIL`.
- `(11)` mfg date == printed mfg date (format-normalized) → else `FAIL`.
- `(17)` exp date == printed exp date → else `FAIL`.
- `(240)` additional product id == REF, applying the rule-set's hyphen policy (see below) →
  match `FLAG`/`PASS` per policy.
- `(01)` GTIN == MXO-PP00006 lookup for this REF →
  - If MXO-PP00006 loaded: equal → `PASS`, unequal → `FAIL`.
  - If MXO-PP00006 not loaded → `DEFERRED` (reason: GTIN source-of-truth not configured).
- If no barcode decodes at all → single `FAIL` (reason "barcode unreadable").

Hyphen policy for `(240)`: GS1 AI 240 is alphanumeric and the encoded value may legitimately
drop the hyphen (`MTUUX400K` vs `MTUUX400-K`). Default behavior: treat as `FLAG` ("AI 240 omits
hyphen present in REF — confirm acceptable per MXO-PP00006") unless the rule set sets
`ai240_hyphen: optional`, in which case `PASS`.

*V11022719 expected:* PASS on (10)/(11)/(17); `FLAG` on (240) hyphen; `DEFERRED` on (01) GTIN
(MXO-PP00006 not yet supplied). Net for Check C: `PASS` with a flag + a deferred sub-item.

## Check D — Description normalization

**Source:** WI052 §3.5.

The same REF appears with different description wording across documents (label "TIBIAL BASE
PLATE / SIZE 4"; CoCs "TIBIAL BASE 4 METALBACKED"; Sterile Lot Record "Tibial Base Plate, Size
4"). These are not string-identical.
- If MXO-PP00001 supplies a canonical label description per REF: compare the label's description
  to the canonical one using the rule-set's match mode (`exact` | `normalized` | `contains`).
  Match → `PASS`, else `FAIL`.
- If MXO-PP00001 not loaded → `DEFERRED` (reason: canonical description source not configured).
  Do **not** attempt to guess equivalence and pass/fail on it.

*V11022719 expected:* `DEFERRED` (MXO-PP00001 not yet supplied).

## Check E — IFU linkage

**Source:** WI052 §3.5; sterile CoC lists applicable IFU(s).

- Determine the IFU(s) the sterile CoC assigns to this REF (e.g., MXO-00022 Rev T for standard
  Freedom items; asterisked items use MXO-00229 Rev 01).
- If MXO-PP00001 says an IFU reference must be printed on this label zone: confirm the printed
  IFU matches the sterile-CoC IFU → `PASS`/`FAIL`.
- If MXO-PP00001 not loaded, or label IFU region not legible → `DEFERRED` (reason recorded).

*V11022719 expected:* `DEFERRED` (MXO-PP00001 not supplied; IFU region not confirmed on label).

## Check F — Static / template content

**Source:** WI052 §3.5; governed entirely by MXO-PP00001.

For the product family resolved from REF, verify against MXO-PP00001 the presence/correctness of:
CE mark + notified-body number, manufacturer block, EC REP block, sterilization symbol,
single-use / handling symbols, product-family branding, label revision.
- One cross-check is doable **without** MXO-PP00001: manufacturer address on the label == the
  "shipped-to" Maxx address on the batch CoC → `PASS`/`FAIL` (this is a data check, run it).
- All other static elements: `PASS`/`FAIL` if MXO-PP00001 loaded, else `DEFERRED`.

*V11022719 expected:* manufacturer-address sub-check `PASS`; remaining static items `DEFERRED`.

## Check G — Workflow integrity flags

**Source:** WI052 §3.6–3.9; real anomalies observed in the sample.

G.1 "Barcode scanned & Verified" checkbox state. WI052 §3.6 requires the scan. If the box is
**No** but the form is otherwise approved → `FLAG` ("approval recorded with barcode-scan box
unchecked — verify §3.6 was performed"). If Yes → `PASS`.
G.2 Deviation/NC reference in Sterile Lot Record comments. If a deviation/NC is referenced
(e.g. "Released under deviation 25.17") → `FLAG` ("lot released under deviation <id>; confirm it
does not affect label content"). The deviation document itself is not in scope to fetch unless a
deviations source is configured (see `docs/09`).
G.3 Quantity reconciliation: batch CoC manufactured (40) vs released (38). A reduction is not a
label failure but is surfaced as an informational `FLAG` if unexplained, or downgraded to a note
if a deviation/NC in G.2 plausibly accounts for it.

*V11022719 expected:* G.1 `FLAG` (box = No), G.2 `FLAG` (deviation 25.17), G.3 informational
`FLAG` (40→38). Two material flags drive the overall verdict to `APPROVE_WITH_FLAGS`.

---

## Verdict resolution algorithm

```
if any required document missing OR linkage (A.1/A.2) fails:
    verdict = REJECT   # (technically un-runnable; report the blocking reason)
elif any check result == FAIL:
    verdict = REJECT
elif any check result == FLAG:
    verdict = APPROVE_WITH_FLAGS
else:
    verdict = APPROVE
# DEFERRED never changes the verdict, but is always surfaced prominently.
```

Important: `DEFERRED` items are **not** silent passes. The UI must show, on every
`APPROVE`/`APPROVE_WITH_FLAGS` verdict, a clear "Not machine-verified — your manual
responsibility" panel listing all `DEFERRED` checks. The reviewer signs knowing exactly what the
machine did and did not confirm.

## Human-in-the-loop (non-negotiable)

1. **Final signature** is always human. The engine produces a verdict; it never writes an
   `approvals` row by itself.
2. **Every FLAG** must be individually acknowledged in the UI before "Sign & Release" enables on
   an amber verdict.
3. **Rejection messaging** to Meril is generated by the system (structured discrepancy report)
   but sent by a human (WI052 §3.9).

## Extensibility

Adding ACI (§4.0) or Maxx-printed (§5.0) later means: new document classifiers in Stage 1, a
path selector, and per-path tweaks to A and G (e.g., ACI has no DHR retention step; Maxx-printed
uses WI052-F1 directly). Keep checks B–F path-agnostic so they're reused unchanged.
