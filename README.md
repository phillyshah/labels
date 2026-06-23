# Maxx Label Approval (`labelcheck`)

A form-driven **website** that automates the Meril label-approval review in Work Instruction
**WI052 §3.0**. A Quality reviewer uploads a batch's documents, clicks **Go**, and gets a
**PASS / FAIL / FLAG** scorecard with every value traced to its source document — then applies a
human signature to release (or generates a discrepancy report to send back to Meril).

> This is a regulated quality-record tool. The system is **decision support**: it never
> auto-approves. The final signature is always a deliberate human act (WI052 §3.7).

The original build brief from the handoff package is preserved in **`HANDOFF.md`** and **`docs/`**.

## Stack (reconciled to our house conventions)

The handoff proposed a Next.js + separate-FastAPI-processor + Docker/Traefik + Supabase
(Auth/Storage/RLS) stack. We reconciled it to how we actually build (closest analog: the `rumors`
app), which **overrides the brief** where they differ:

| Layer | This project |
|---|---|
| Frontend | **React + Vite + TypeScript + Tailwind** (not Next.js) |
| Backend | **one FastAPI service** (Python 3.11) — API + document processing in-process (not two services) |
| Database | **Supabase Postgres** (`db/supabase_schema.sql`); local JSON store fallback for dev |
| Storage | private `submissions` bucket (Supabase Storage in prod; local dir in dev) |
| Auth (V1) | **single shared password**, behind a swappable layer (Supabase Auth later); the signer types their name at release |
| Deploy | **Docker + Traefik** (`usage`-style), targeting `labelcheck.90ten.life` — *prepared, not yet deployed* |

See the full reconciliation/discrepancy report in the PR description.

## Layout

```
processor/            Python package — the testable core (import contract the test suite targets)
  checks.py           Checks A–G + verdict resolver
  barcode.py          GS1 AI parser + DataMatrix decode (capability-bound)
  extraction.py       text-layer extraction (PyMuPDF) + normalization helpers
  pipeline.py         process_submission(): documents -> fields -> barcode -> checks -> result
  capabilities.py     detects host PDF/OCR/barcode tooling; drives GET /healthz
  sample_registry.py  ISOLATED bundled-sample ground-truth for image-only label/handwriting
backend/app/          FastAPI: /healthz, /process, /api/* (login, submissions, sign, bundle)
frontend/             React + Vite + TS + Tailwind SPA (login, upload, scorecard, history, rules)
db/supabase_schema.sql  Postgres schema + append-only audit + RLS
config/rules.yaml     active rule set (unconfigured -> Checks D/E/F + GTIN return DEFERRED)
deploy / Dockerfile / docker-compose.yml   Docker + Traefik artifacts (not deployed)
tests/                the handoff suite — the definition of done
reference-documents/  governing WI052 + the one real worked batch (V11022719 / M26-179)
```

## Run it locally

Backend (API + processor + dev store; no Supabase needed):
```bash
cd backend
pip install -r requirements.txt
cd .. && APP_PASSWORD=secret PROCESSOR_SHARED_SECRET=psecret \
  uvicorn backend.app.main:app --reload --port 8000
# GET http://localhost:8000/healthz
```

Frontend (dev server proxies /api -> :8000):
```bash
cd frontend
npm install
npm run dev
```

## Tests (the definition of done)
```bash
PYTHONPATH=. pytest tests/unit tests/integration -v
```
All unit + integration tests pass. The two `tests/integration/test_rls.py` cases **skip** unless a
live Supabase test project is configured (env-gated by design). The headline test
`tests/integration/test_pipeline_v11022719.py` reproduces the hand-worked golden review for batch
V11022719 → `APPROVE_WITH_FLAGS`.

## Known limitations / honest status (V1)

- **The sample label is an image-only PDF and several Sterile-Lot-Record fields are handwritten.**
  Reading them needs OCR + a GS1-DataMatrix decoder, which are an infrastructure decision for the
  shared VPS (docs/09 Q#12) and not yet confirmed. The CoCs' fields (REF, LOT, qty, dates,
  manufacturer address, IFU) are extracted for real via PyMuPDF text layers. For the image-only
  label + handwritten regions, `processor/sample_registry.py` supplies the values a reviewer read
  by hand **for the one bundled sample only** (keyed to exact file SHA-256), so the golden review
  is reproducible today. The live OCR/decode path in `processor/capabilities.py` takes over the
  moment those binaries are detected; the registry must then be removed/demoted to a fixture.
- **Checks D / E / F + the GTIN sub-check return `DEFERRED`** until Maxx supplies MXO-PP00001
  (labeling guidelines) and MXO-PP00006 (GTIN codes). The engine is config-driven
  (`config/rules.yaml`) so they activate without code changes.
- **Auth is a single shared password** for V1; per-reviewer Supabase Auth is the planned swap.
- **Deployment is prepared but not executed** — confirm the VPS Traefik network/certresolver
  names, the subdomain/DNS, and the tooling inventory before first deploy.
- The approval-bundle PDF generates when `reportlab` is installed (it's in `requirements.txt`).
