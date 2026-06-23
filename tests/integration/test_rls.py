"""
Integration test: Supabase Row Level Security isolation.

Reviewer A must not be able to read Reviewer B's submission. This guards the multi-user
confidentiality requirement in docs/03-supabase-schema.md.

Requires a test Supabase project (local `supabase start` or a dedicated test project).
Set env: TEST_SUPABASE_URL, TEST_SUPABASE_ANON_KEY, and two seeded reviewer logins.

This is a skeleton -- the team wires it to their Supabase client. It is marked skip until the
test project env is configured so the rest of the suite runs without Supabase.
"""

import os
import pytest

REQUIRED_ENV = ["TEST_SUPABASE_URL", "TEST_SUPABASE_ANON_KEY",
                "TEST_REVIEWER_A_JWT", "TEST_REVIEWER_B_JWT"]

pytestmark = pytest.mark.skipif(
    not all(os.environ.get(k) for k in REQUIRED_ENV),
    reason="Supabase test project env not configured",
)


def _client(jwt):
    from supabase import create_client  # supabase-py
    c = create_client(os.environ["TEST_SUPABASE_URL"], os.environ["TEST_SUPABASE_ANON_KEY"])
    c.postgrest.auth(jwt)
    return c


def test_reviewer_cannot_read_others_submission():
    a = _client(os.environ["TEST_REVIEWER_A_JWT"])
    b = _client(os.environ["TEST_REVIEWER_B_JWT"])

    created = a.table("submissions").insert({
        "ref": "MTUUX400-K", "lot": "V11022719", "sterile_lot": "M26-179",
        "status": "uploaded",
    }).execute()
    sub_id = created.data[0]["id"]

    # Reviewer B must NOT see Reviewer A's row.
    seen = b.table("submissions").select("*").eq("id", sub_id).execute()
    assert seen.data == [], "RLS leak: reviewer B read reviewer A's submission"


def test_approvals_are_immutable():
    a = _client(os.environ["TEST_REVIEWER_A_JWT"])
    sub = a.table("submissions").insert({"status": "uploaded"}).execute().data[0]
    appr = a.table("approvals").insert({
        "submission_id": sub["id"], "decision": "RELEASED",
        "signed_by_name": "Reviewer A",
    }).execute().data[0]

    with pytest.raises(Exception):
        a.table("approvals").update({"decision": "REJECTED"}).eq("id", appr["id"]).execute()
