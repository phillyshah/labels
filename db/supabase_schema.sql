-- Maxx Label Approval — Supabase Postgres schema (docs/03-supabase-schema.md)
-- Run in the Supabase SQL editor (the project's convention) or via a migration tool.
-- Idempotent-ish: safe to re-run during V1 setup.

-- ---------------------------------------------------------------------------
-- profiles: app-level user metadata + role.
-- Kept now so the future swap from the V1 shared-password gate to Supabase Auth
-- is purely additive (link profiles.id -> auth.users.id at that point).
-- ---------------------------------------------------------------------------
create table if not exists profiles (
  id          uuid primary key,            -- becomes references auth.users(id) on Supabase Auth swap
  full_name   text not null,
  role        text not null check (role in ('reviewer','admin')),
  created_at  timestamptz not null default now()
);

-- submissions: one row per review run.
create table if not exists submissions (
  id              uuid primary key default gen_random_uuid(),
  created_by      uuid references profiles(id),
  created_at      timestamptz not null default now(),
  ref             text,
  lot             text,
  sterile_lot     text,
  status          text not null default 'uploaded'
                  check (status in ('uploaded','processing','reviewed','released','rejected','error')),
  verdict         text check (verdict in ('APPROVE','APPROVE_WITH_FLAGS','REJECT')),
  processor_ms    integer,
  rules_version   text,
  error_detail    text,
  result_json     jsonb           -- full processor result (source-of-truth table, barcode, full
                                  -- identity, per-check evidence) so the scorecard + signed bundle
                                  -- can be rebuilt faithfully; check_results stays the queryable index.
);

-- Backfill for projects created before result_json existed (safe to re-run).
alter table submissions add column if not exists result_json jsonb;

-- Training batches are processed like any submission but never signed; they exist to collect
-- reviewer feedback that drives rule/config tuning (and, later, an LLM-assist step).
alter table submissions add column if not exists is_training boolean not null default false;

-- feedback: per-check (or per-verdict) reviewer judgement on a processed batch. The labeled
-- corpus the training section accumulates; queryable for the accuracy dashboard.
create table if not exists feedback (
  id              uuid primary key default gen_random_uuid(),
  submission_id   uuid not null references submissions(id) on delete cascade,
  target          text not null,          -- 'A'..'G', 'verdict', or a field name
  rating          text not null check (rating in ('correct','wrong','partial')),
  expected        text,                   -- optional: what the right answer should have been
  note            text,                   -- free-text reviewer comment
  created_by_name text,
  created_at      timestamptz not null default now()
);
create index if not exists feedback_submission_idx on feedback(submission_id);

-- check_results: one row per individual check, per submission.
create table if not exists check_results (
  id            uuid primary key default gen_random_uuid(),
  submission_id uuid not null references submissions(id) on delete cascade,
  check_code    text not null,
  check_name    text not null,
  result        text not null check (result in ('PASS','FAIL','FLAG','DEFERRED')),
  reason        text not null default '',
  evidence      jsonb not null default '{}'::jsonb,
  created_at    timestamptz not null default now()
);

-- approvals: the signing action (immutable once written).
create table if not exists approvals (
  id                 uuid primary key default gen_random_uuid(),
  submission_id      uuid not null unique references submissions(id),
  decision           text not null check (decision in ('RELEASED','REJECTED')),
  signed_by          uuid references profiles(id),
  signed_by_name     text not null,
  signed_at          timestamptz not null default now(),
  acknowledged_flags jsonb,
  bundle_path        text
);

-- audit_log: append-only trail of every meaningful action.
create table if not exists audit_log (
  id            bigserial primary key,
  submission_id uuid references submissions(id),
  actor         uuid references profiles(id),
  action        text not null,
  detail        jsonb not null default '{}'::jsonb,
  at            timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Append-only enforcement for audit_log (and conceptually for approvals).
-- ---------------------------------------------------------------------------
revoke update, delete on audit_log from authenticated, anon, service_role;

create or replace function deny_mutation() returns trigger as $$
begin raise exception 'this table is append-only'; end;
$$ language plpgsql;

drop trigger if exists audit_no_update on audit_log;
drop trigger if exists audit_no_delete on audit_log;
create trigger audit_no_update before update on audit_log
  for each row execute function deny_mutation();
create trigger audit_no_delete before delete on audit_log
  for each row execute function deny_mutation();

-- approvals are immutable once written: block updates/deletes.
revoke update, delete on approvals from authenticated, anon;
drop trigger if exists approvals_no_update on approvals;
drop trigger if exists approvals_no_delete on approvals;
create trigger approvals_no_update before update on approvals
  for each row execute function deny_mutation();
create trigger approvals_no_delete before delete on approvals
  for each row execute function deny_mutation();

-- ---------------------------------------------------------------------------
-- Row Level Security.
-- The processor/web service writes with the service-role key (bypasses RLS); the policies below
-- constrain end-user (authenticated) access once Supabase Auth is enabled. A reviewer sees only
-- their own submissions; admins see all. tests/integration/test_rls.py asserts this isolation.
-- ---------------------------------------------------------------------------
alter table profiles      enable row level security;
alter table submissions   enable row level security;
alter table check_results enable row level security;
alter table approvals     enable row level security;
alter table audit_log     enable row level security;

-- profiles: a user reads their own row; admins read all.
drop policy if exists profiles_self_read on profiles;
create policy profiles_self_read on profiles for select to authenticated
  using (id = auth.uid() or exists (
    select 1 from profiles p where p.id = auth.uid() and p.role = 'admin'));

-- submissions: reviewer reads/inserts their own; admins read all.
drop policy if exists submissions_owner_rw on submissions;
create policy submissions_owner_rw on submissions for select to authenticated
  using (created_by = auth.uid() or exists (
    select 1 from profiles p where p.id = auth.uid() and p.role = 'admin'));
drop policy if exists submissions_owner_insert on submissions;
create policy submissions_owner_insert on submissions for insert to authenticated
  with check (created_by = auth.uid());

-- check_results: visible to whoever can see the parent submission.
drop policy if exists check_results_via_submission on check_results;
create policy check_results_via_submission on check_results for select to authenticated
  using (exists (select 1 from submissions s
                 where s.id = submission_id
                   and (s.created_by = auth.uid()
                        or exists (select 1 from profiles p
                                   where p.id = auth.uid() and p.role = 'admin'))));

-- approvals: reviewer may insert for a submission they own; nobody updates/deletes; admins read.
drop policy if exists approvals_owner_insert on approvals;
create policy approvals_owner_insert on approvals for insert to authenticated
  with check (exists (select 1 from submissions s
                      where s.id = submission_id and s.created_by = auth.uid()));
drop policy if exists approvals_read on approvals;
create policy approvals_read on approvals for select to authenticated
  using (exists (select 1 from submissions s
                 where s.id = submission_id
                   and (s.created_by = auth.uid()
                        or exists (select 1 from profiles p
                                   where p.id = auth.uid() and p.role = 'admin'))));

-- audit_log: insert-only for authenticated; admins (and owning reviewer) read.
drop policy if exists audit_insert on audit_log;
create policy audit_insert on audit_log for insert to authenticated with check (true);
drop policy if exists audit_read on audit_log;
create policy audit_read on audit_log for select to authenticated
  using (exists (select 1 from profiles p where p.id = auth.uid() and p.role = 'admin')
         or exists (select 1 from submissions s
                    where s.id = submission_id and s.created_by = auth.uid()));

-- ---------------------------------------------------------------------------
-- Storage: create a PRIVATE bucket named 'submissions' in the Supabase dashboard
-- (Storage -> New bucket -> uncheck "Public"). Inputs and generated bundles live there;
-- the service mints short-lived signed URLs for browser access. See docs/03.
-- ---------------------------------------------------------------------------
