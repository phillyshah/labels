# 06 — Frontend Specification

Form-driven, deliberately boring, fast to use. A reviewer should be able to complete a review in
under a minute when the verdict is clean. Build with the design constraints in
`/mnt/skills/public/frontend-design` conventions if your team uses that system; otherwise keep
it clean, high-contrast, and accessible. This is a quality tool, not a marketing site.

## Auth gate

- Supabase Auth. Unauthenticated users see only a login screen.
- After login, route by role: `reviewer` → review workspace; `admin` → review workspace + rules
  admin.

## Screen 1 — New Review (the upload form)

Single form, four required file inputs + two optional:

```
┌─ New Label Review ────────────────────────────────────────────┐
│  Reviewer: [logged-in name]                                    │
│                                                                │
│  Label form (Reference Label 1st Copy) .......... [ Choose ] ● │
│  Batch CoC ...................................... [ Choose ] ● │
│  Sterile Lot CoC ................................ [ Choose ] ● │
│  Sterile Lot Record ............................. [ Choose ] ● │
│  Documentation Release Verification (optional) .. [ Choose ] ○ │
│  Sterile Product Release Verification (optional)  [ Choose ] ○ │
│                                                                │
│                                          [   Go   ]            │
└────────────────────────────────────────────────────────────────┘
```

- Accept PDF (and image for the label, if a scan). Validate type + size client-side.
- On selecting files, optionally auto-classify and show a green check when the expected document
  type is recognized (calls a lightweight `/classify` or does it after upload — your call).
- **Go** uploads to Supabase Storage, creates the submission, calls the processor, and navigates
  to Screen 2 with a progress indicator ("Processing — usually under 30s").
- Do **not** use a raw HTML `<form>` submit if building in React per the artifact constraints;
  use controlled inputs + an `onClick` handler.

## Screen 2 — Verdict & Scorecard

Top: a verdict banner.

```
┌──────────────────────────────────────────────────────────────┐
│  ✔ APPROVE         /  ▲ APPROVE WITH FLAGS  /  ✖ REJECT        │
│  REF MTUUX400-K · LOT V11022719 · Sterile lot M26-179         │
└──────────────────────────────────────────────────────────────┘
```

Then the scorecard table — one row per check:

| Check | Name | Result | Reason |
|---|---|---|---|
| A | Completeness / linkage / signatures | PASS | ... |
| B | Cross-document consistency | PASS | ... |
| C | Barcode decode & match | PASS (1 flag, 1 deferred) | ... |
| D | Description normalization | DEFERRED | MXO-PP00001 not configured |
| E | IFU linkage | DEFERRED | ... |
| F | Static content | DEFERRED (addr sub-check PASS) | ... |
| G | Workflow integrity | 2 FLAGS | barcode box = No; deviation 25.17 |

- Color: PASS green, FAIL red, FLAG amber, DEFERRED grey.
- Each row expands to show the **evidence**: the exact values compared and the source document +
  page for each, with a thumbnail / link to view that region of the PDF.

Two always-visible panels below the scorecard:

- **Flags to acknowledge** (amber verdicts): each flag has an "Acknowledge" toggle + a free-text
  note field. "Sign & Release" stays disabled until all are acknowledged.
- **Not machine-verified (DEFERRED)**: lists every deferred check so the reviewer knows what
  remains their manual responsibility. Cannot be dismissed; signing implies they accept it.

## Screen 2 actions

- `APPROVE` / `APPROVE_WITH_FLAGS`: **[ Sign & Release ]** (amber: enabled only after all flags
  acknowledged). Captures the reviewer identity + timestamp, writes the `approvals` row,
  generates the approval bundle PDF, writes the audit entry, sets status `released`.
- `REJECT`: **[ Generate Discrepancy Report ]** — produces a structured PDF/JSON listing each
  failed field with conflicting values + sources, ready to email to Meril (WI052 §3.9). Sets
  status `rejected`. A human sends the email.
- Both: **[ View Documents ]** to open any source PDF.

## Screen 3 — History

A table of past submissions (filtered by RLS): date, reviewer, REF, LOT, sterile lot, verdict,
decision, link to the bundle. Read-only. This is the searchable record set the project owner
originally wanted ("each time we need to run this process … get this type of output").

## Screen 4 — Rules admin (admin role only)

- View the active rule set (`config/rules.yaml` content / `rules` table), its version, and when
  MXO-PP00001 / MXO-PP00006 were last updated.
- Upload / edit the rule set. Saving bumps the version and writes a `RULES_UPDATE` audit entry.
- This is how `DEFERRED` checks become live `PASS`/`FAIL` checks once Maxx supplies the real
  labeling guideline and GTIN data.

## Generated approval bundle (PDF)

Mirrors WI052-F1 plus the evidence. One PDF containing: the filled approval record (Item #, Qty,
Lot #, Description, Outer/Inner label thumbnails, Comments, Barcode Scanned & Verified state,
Quality Approval = reviewer name + timestamp), the full scorecard, the evidence pack, and the
audit summary. This is the DHR artifact.

## Empty / error states

- Processor error or missing document → clear message naming what's wrong, with a "Back to
  upload" action. Never show a half-rendered scorecard.
- Low-confidence extraction → the affected rows show a small "read with low confidence" badge.
