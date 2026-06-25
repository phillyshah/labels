# 03 — Supabase: Schema, Storage, Auth

Supabase provides Postgres, Storage, and Auth. This doc defines all three. Treat the SQL below
as the migration baseline; refine types as needed but keep the shape and the constraints.

## Auth

- Use Supabase Auth (email + password, or SSO if 90ten.life already federates — confirm in 09).
- One role matters for this phase: **`reviewer`** (a Maxx Quality representative who can run
  reviews and sign approvals). Add an **`admin`** role for managing the rule set and viewing all
  records.
- Store role in a `profiles` table keyed to `auth.users.id`.
- The signing reviewer's identity (name + user id + timestamp) is captured on every approval —
  this is the digital equivalent of the handwritten "Maxx Approval" signature in WI052 §3.7.

## Storage

One **private** bucket: `submissions`.

```
submissions/
  {submission_id}/
    inputs/
      label.pdf
      batch_coc.pdf
      sterile_coc.pdf
      sterile_lot_record.pdf
      [optional] doc_release_verification.pdf
      [optional] sterile_product_release_verification.pdf
    outputs/
      approval_bundle.pdf        # generated on release
      discrepancy_report.pdf     # generated on reject
      evidence.json              # machine-readable evidence pack
```

- Bucket is **not** public. Access only via short-lived signed URLs minted server-side.
- The processor reads inputs via signed URLs (or the service-role client). It writes
  `evidence.json`. `web` writes the generated PDFs.

## Database schema

```sql
-- profiles: app-level user metadata + role
create table profiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  full_name   text not null,
  role        text not null check (role in ('reviewer','admin')),
  created_at  timestamptz not null default now()
);

-- submissions: one row per review run
create table submissions (
  id              uuid primary key default gen_random_uuid(),
  created_by      uuid not null references profiles(id),
  created_at      timestamptz not null default now(),
  -- identity parsed from documents (filled by processor)
  ref             text,          -- e.g. MTUUX400-K
  lot             text,          -- e.g. V11022719
  sterile_lot     text,          -- e.g. M26-179
  status          text not null default 'uploaded'
                  check (status in ('uploaded','processing','reviewed','released','rejected','error')),
  verdict         text           -- APPROVE | APPROVE_WITH_FLAGS | REJECT (set by processor)
                  check (verdict in ('APPROVE','APPROVE_WITH_FLAGS','REJECT')),
  processor_ms    integer,       -- run duration
  rules_version   text,          -- which rules.yaml version ran
  error_detail    text
);

-- check_results: one row per individual check, per submission
create table check_results (
  id            uuid primary key default gen_random_uuid(),
  submission_id uuid not null references submissions(id) on delete cascade,
  check_code    text not null,   -- 'A','B','C','D','E','F','G' or finer sub-codes
  check_name    text not null,
  result        text not null check (result in ('PASS','FAIL','FLAG','DEFERRED')),
  reason        text not null,   -- one-line human-readable explanation
  evidence      jsonb not null,  -- the values compared + their source documents
  created_at    timestamptz not null default now()
);

-- approvals: the signing action (immutable once written)
create table approvals (
  id              uuid primary key default gen_random_uuid(),
  submission_id   uuid not null unique references submissions(id),
  decision        text not null check (decision in ('RELEASED','REJECTED')),
  signed_by       uuid not null references profiles(id),
  signed_by_name  text not null,           -- denormalized for the permanent record
  signed_at       timestamptz not null default now(),
  acknowledged_flags jsonb,                -- which flags the reviewer acknowledged (amber path)
  bundle_path     text                     -- storage path of generated PDF bundle
);

-- audit_log: append-only trail of every meaningful action
create table audit_log (
  id            bigserial primary key,
  submission_id uuid references submissions(id),
  actor         uuid references profiles(id),
  action        text not null,   -- 'UPLOAD','RUN','VERDICT','SIGN','REJECT','RULES_UPDATE'
  detail        jsonb not null,
  at            timestamptz not null default now()
);
```

## Append-only audit log (enforced)

Make `audit_log` truly append-only at the DB level:

```sql
revoke update, delete on audit_log from authenticated, anon, service_role;

-- belt-and-braces: block updates/deletes via trigger too
create or replace function deny_mutation() returns trigger as $$
begin raise exception 'audit_log is append-only'; end;
$$ language plpgsql;

create trigger audit_no_update before update on audit_log
  for each row execute function deny_mutation();
create trigger audit_no_delete before delete on audit_log
  for each row execute function deny_mutation();
```

Do the same conceptually for `approvals`: once a row exists, it must not change. A re-review of
the same batch creates a **new** submission, never edits a prior approval.

## Row Level Security (sketch)

Enable RLS on every table. Baseline policies:

- `profiles`: a user can read their own row; admins read all.
- `submissions` / `check_results`: a `reviewer` can read/insert their own submissions; admins
  read all. The processor writes via the service-role key (bypasses RLS) — keep that key
  server-side only.
- `approvals`: a reviewer can insert an approval for a submission they own; nobody can update or
  delete. Admins read all.
- `audit_log`: insert-only for authenticated users; select for admins (and the owning reviewer
  for their own submissions).

Write the exact policies during implementation and include them in the migration. Test them:
the test suite includes an RLS test stub (`tests/integration`) — a reviewer must not be able to
read another reviewer's submission.

## Rules storage

The active rule set (`config/rules.yaml`, derived from MXO-PP00001 / MXO-PP00006 when supplied)
can live either as a file mounted into the processor (`RULES_PATH`) or as a `rules` table in
Postgres with a `version` column. A table is preferable because updates are audited
(`RULES_UPDATE` action) and versioned without a redeploy. Either way, the version that ran a
given submission is recorded in `submissions.rules_version`.
