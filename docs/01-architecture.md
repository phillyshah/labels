# 01 — Architecture

## Components

```
                          ┌──────────────────────────────────────────┐
                          │   Traefik (reverse proxy + TLS)           │
                          │   labelcheck.90ten.life  ──► routes       │
                          └───────────────┬───────────────┬──────────┘
                                          │               │
                        /  (UI + API)     │               │  /process (internal)
                                          ▼               ▼
                        ┌─────────────────────┐   ┌────────────────────────┐
                        │  web  (Next.js)     │   │  processor (FastAPI/PY) │
                        │  - upload form      │──►│  - PDF/image parsing    │
                        │  - run + review UI  │   │  - field extraction     │
                        │  - sign & release   │   │  - barcode decode       │
                        │  - calls Supabase   │   │  - checks engine        │
                        └──────────┬──────────┘   └───────────┬────────────┘
                                   │                          │
                                   ▼                          ▼
                        ┌────────────────────────────────────────────────┐
                        │  Supabase                                       │
                        │  - Postgres (submissions, results, audit log)   │
                        │  - Storage (uploaded PDFs, generated bundles)   │
                        │  - Auth (Quality reviewers)                     │
                        └────────────────────────────────────────────────┘
```

## Why this split

- **`web` (Next.js, App Router):** Handles auth, the upload form, the review/sign UI, and
  orchestration. Talks to Supabase directly for auth/storage/DB and calls the processor for the
  heavy document work. Next.js deploys cleanly as a Docker container behind Traefik and has
  first-class Supabase support.
- **`processor` (Python, FastAPI):** Document processing (PDF text + image extraction, OCR,
  barcode decoding) is dramatically stronger in the Python ecosystem and—critically—the VPS
  already has Python document tooling installed for other projects (see
  `docs/04-processing-pipeline.md`). Keep it a separate service so the document toolchain is
  isolated, independently scalable, and independently testable. The checks engine lives here
  because it operates directly on extracted fields.
- **Supabase:** Single backend for relational data, file storage, and authentication. No
  separate auth server or object store needed.

If your team is strongly Node-only, the processor *can* be Node, but you will be fighting the
barcode/OCR ecosystem and re-installing tooling the VPS already has. Default to Python.

## Request flow (one review)

1. Reviewer authenticates (Supabase Auth) and opens the upload form in `web`.
2. Reviewer uploads the 4 documents. `web` stores them in a Supabase Storage bucket
   (`submissions/{submission_id}/...`) and inserts a `submissions` row (status `uploaded`).
3. Reviewer clicks **Go**. `web` calls the processor `POST /process` with the submission id and
   signed URLs (or streams the files). Status → `processing`.
4. `processor` downloads the files, runs the pipeline (`docs/04`), runs the checks (`docs/05`),
   and returns a structured result (`docs/07`). It also writes the result rows to Postgres.
5. `web` renders the scorecard. Reviewer reviews flags.
6. Reviewer clicks **Sign & Release** (or **Generate Discrepancy Report**). `web` writes the
   signature/verdict to the `approvals` table, locks the record, generates the PDF bundle, and
   writes an immutable `audit_log` entry. Status → `released` or `rejected`.

## Containers & runtime

- Each service ships as a Docker image. Use a single `docker-compose.yml` (or the equivalent
  the VPS already uses) bringing up `web`, `processor`, and Traefik. Supabase is hosted (cloud)
  or self-hosted depending on what 90ten.life already runs — confirm in `docs/09`.
- All inter-service calls stay on the internal Docker network. Only Traefik is exposed.
- The processor's `/process` route is **not** exposed publicly through Traefik; only `web`
  reaches it on the internal network. (If you must expose it, lock it behind a shared secret /
  mTLS — it ingests quality documents.)

## Security posture (summary; details in 02 and 03)

- TLS terminated at Traefik (Let's Encrypt).
- Supabase Row Level Security on every table; reviewers see only what their role permits.
- Uploaded documents and generated bundles live in a **private** storage bucket; access via
  short-lived signed URLs only.
- Audit log is append-only (enforced at the DB level — see `docs/03`).
- No PHI is involved (these are device/lot records, not patient data), but treat all content as
  confidential quality records.

## Statelessness

The processor holds no state between requests. Everything needed for a run is passed in or
fetched from Supabase. This makes it safe to scale horizontally and trivial to test.
