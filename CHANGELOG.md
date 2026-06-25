# Changelog

All notable changes to Label Approval are recorded here.
Versions follow [Semantic Versioning](https://semver.org/). The user-facing
("What's New") copy lives in `backend/app/version.py`; this file is the
developer-facing record.

---

## [1.5.0] — 2026-06-25

### Added
- **Editable Rules screen** — the rule set that drives Checks C-AI(01), D, E and
  F is now edited in-app instead of by hand-editing `config/rules.yaml`. Each
  section has an Active/Deferred toggle, structured REF→value editors (GTIN map,
  description map, REF→family map), the AI(240) hyphen policy + description
  match-mode selectors, and a JSON editor for per-family static content.
- **`GET /api/rules`** — returns the full active rule set (auth required).
- **`PUT /api/rules`** — validates, normalizes REF keys (uppercase/trim, so
  engine lookups can't silently miss), persists to the active rules file, and
  writes a `RULES_UPDATE` audit entry. Returns the saved (normalized) rules.

### Changed
- **`config.py`** — added `validate_rules()` and `save_rules()`; the latter
  merges over section defaults so a partial payload never drops required keys.

## [1.4.0] — 2026-06-25

### Added
- **`backend/app/version.py`** — single source of truth for `VERSION` + the
  user-facing changelog, mirroring the convention used across the other
  projects.
- **`GET /version`** — returns the current version and full changelog
  (unauthenticated; no sensitive data).
- **"What's New" panel** — header button labelled `What's New · vX`, opens a
  modal of release cards (closes via X, backdrop, or Esc). Version is also shown
  in the footer.
- **In-app user guide** — a `?` button in the header opens a side drawer with a
  quick guide to running a review, reading the verdict, and using Training.

## [1.3.0] — 2026-06-24

### Added
- **Ground-truth auto-scoring** in Training: a reviewer can supply the expected
  verdict + per-check expected results and auto-score the tool's output against
  them in one click. Expected values are stored on each feedback row. Manual
  per-check annotation remains available (both modes supported).
- **AI-suggested rule edits** (`backend/app/assist.py`): sends the reviewer
  disagreements (rating ≠ correct, enriched with the tool's own output for that
  check) plus the current rule config to the Claude API and returns concrete,
  reviewable change proposals. Never applies anything — a human applies what they
  accept. Inert and safe when `ANTHROPIC_API_KEY` is unset.
- **`POST /api/training/suggest`** endpoint and a Training-screen panel rendering
  the drafted suggestions.
- `store.disagreement_corpus()` (Local + Postgres) assembles the AI-assist input
  by joining feedback to each batch's stored result.

### Dependencies
- Added `anthropic` (optional; the suggest endpoint degrades gracefully without
  a key).

## [1.2.0] — 2026-06-24

### Added
- **Training tab**: re-run a past batch and rate each check
  (correct / partial / wrong) with notes, building a labeled corpus.
- **Accuracy dashboard**: overall + per-check agreement between the tool and
  reviewer ratings.
- `feedback` table + `submissions.is_training` column; `training_metrics()` on
  both stores.

## [1.1.0] — 2026-06-24

### Added
- Drag-and-drop document upload, with each required/optional document slotted
  (`FileRow` component).
- Template-match validation: each uploaded document is classified against its
  expected type and mismatches are surfaced before the checks run
  (`processor/classify.py`).
- Narrative prose summary opening the discrepancy report (Section 2), not just a
  table of check results.

## [1.0.0] — 2026-06-23

### Added
- Initial release: upload a label packet → automated approval checks (A–G) with
  an APPROVE / APPROVE-WITH-FLAGS / REJECT verdict.
- Cross-checks the label against the batch CoC and sterilization records; GS1
  DataMatrix barcode decode for device identity.
- Approval-bundle and discrepancy-report PDF generation.
- Shared-password gate; Postgres (Supabase) persistence with a local JSON
  fallback.
