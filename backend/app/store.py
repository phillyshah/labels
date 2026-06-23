"""Persistence layer with two interchangeable backends.

- `PostgresStore`  -> Supabase Postgres (the production target; schema in db/supabase_schema.sql).
- `LocalStore`     -> JSON + on-disk files, used automatically when DATABASE_URL is unset so the
                      app runs end-to-end in development without Supabase.

Both expose the same interface, so the API layer is storage-agnostic. Uploaded documents and
generated bundles live under a private location (Supabase Storage bucket in prod, a gitignored
local dir in dev); the API only ever hands the browser short-lived references, never raw paths.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .config import settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


class LocalStore:
    """Filesystem-backed store for development (no Supabase required)."""

    def __init__(self, root: Optional[str] = None):
        self.root = Path(root or settings().local_data_dir)
        (self.root / "uploads").mkdir(parents=True, exist_ok=True)
        self._db = self.root / "db.json"
        if not self._db.exists():
            self._write({"submissions": {}, "check_results": [], "approvals": {}, "audit_log": []})

    # --- internals ---
    def _read(self) -> Dict:
        return json.loads(self._db.read_text())

    def _write(self, data: Dict) -> None:
        self._db.write_text(json.dumps(data, indent=2, default=str))

    # --- submissions ---
    def create_submission(self, identity: Optional[Dict] = None) -> str:
        sid = _new_id()
        data = self._read()
        data["submissions"][sid] = {
            "id": sid, "created_at": _now(), "status": "uploaded",
            "verdict": None, "rules_version": None, "processor_ms": None,
            "ref": (identity or {}).get("ref"), "lot": (identity or {}).get("lot"),
            "sterile_lot": (identity or {}).get("sterile_lot"), "error_detail": None,
        }
        self._write(data)
        return sid

    def save_input_file(self, submission_id: str, doc_type: str, filename: str,
                        content: bytes) -> str:
        d = self.root / "uploads" / submission_id / "inputs"
        d.mkdir(parents=True, exist_ok=True)
        ext = Path(filename).suffix or ".pdf"
        path = d / f"{doc_type}{ext}"
        path.write_bytes(content)
        return str(path)

    def set_result(self, submission_id: str, result: Dict) -> None:
        data = self._read()
        sub = data["submissions"].get(submission_id)
        if not sub:
            return
        ident = result.get("identity", {})
        sub.update({
            "status": "reviewed", "verdict": result.get("verdict"),
            "rules_version": result.get("rules_version"),
            "processor_ms": result.get("processor_ms"),
            "ref": ident.get("ref"), "lot": ident.get("lot"),
            "sterile_lot": ident.get("sterile_lot"),
        })
        data["check_results"] = [c for c in data["check_results"]
                                 if c.get("submission_id") != submission_id]
        for c in result.get("checks", []):
            data["check_results"].append({"submission_id": submission_id, **c})
        sub["_result"] = result  # full result cached for the scorecard view
        self._write(data)

    def set_error(self, submission_id: str, error: Dict) -> None:
        data = self._read()
        sub = data["submissions"].get(submission_id)
        if sub:
            sub.update({"status": "error", "error_detail": error.get("detail"),
                        "_result": error})
            self._write(data)

    def get_submission(self, submission_id: str) -> Optional[Dict]:
        return self._read()["submissions"].get(submission_id)

    def list_submissions(self) -> List[Dict]:
        subs = list(self._read()["submissions"].values())
        return sorted(subs, key=lambda s: s["created_at"], reverse=True)

    # --- approvals + audit ---
    def create_approval(self, submission_id: str, decision: str, signed_by_name: str,
                        acknowledged_flags: Optional[List] = None,
                        bundle_path: Optional[str] = None) -> Dict:
        data = self._read()
        if submission_id in data["approvals"]:
            raise ValueError("approval already exists for this submission (immutable)")
        approval = {
            "id": _new_id(), "submission_id": submission_id, "decision": decision,
            "signed_by_name": signed_by_name, "signed_at": _now(),
            "acknowledged_flags": acknowledged_flags or [], "bundle_path": bundle_path,
        }
        data["approvals"][submission_id] = approval
        sub = data["submissions"].get(submission_id)
        if sub:
            sub["status"] = "released" if decision == "RELEASED" else "rejected"
        self._write(data)
        return approval

    def get_approval(self, submission_id: str) -> Optional[Dict]:
        return self._read()["approvals"].get(submission_id)

    def append_audit(self, action: str, submission_id: Optional[str] = None,
                     actor: Optional[str] = None, detail: Optional[Dict] = None) -> None:
        data = self._read()
        data["audit_log"].append({
            "id": len(data["audit_log"]) + 1, "submission_id": submission_id,
            "actor": actor, "action": action, "detail": detail or {}, "at": _now(),
        })
        self._write(data)


class PostgresStore(LocalStore):
    """Supabase Postgres store. Reuses LocalStore for on-disk file storage in V1 (Supabase

    Storage upload is wired where the bucket is configured), and overrides the relational
    operations to hit Postgres via psycopg against db/supabase_schema.sql.
    """

    def __init__(self):
        # Still keep a local dir for file bytes until Supabase Storage upload is enabled.
        super().__init__()
        import psycopg  # lazy: only needed when a database is configured
        self._connect = lambda: psycopg.connect(settings().database_url, autocommit=True)

    def create_submission(self, identity: Optional[Dict] = None) -> str:
        sid = _new_id()
        with self._connect() as con:
            con.execute(
                "insert into submissions (id, ref, lot, sterile_lot, status) "
                "values (%s,%s,%s,%s,'uploaded')",
                (sid, (identity or {}).get("ref"), (identity or {}).get("lot"),
                 (identity or {}).get("sterile_lot")),
            )
        return sid

    def set_result(self, submission_id: str, result: Dict) -> None:
        ident = result.get("identity", {})
        with self._connect() as con:
            con.execute(
                "update submissions set status='reviewed', verdict=%s, rules_version=%s, "
                "processor_ms=%s, ref=%s, lot=%s, sterile_lot=%s where id=%s",
                (result.get("verdict"), result.get("rules_version"), result.get("processor_ms"),
                 ident.get("ref"), ident.get("lot"), ident.get("sterile_lot"), submission_id),
            )
            con.execute("delete from check_results where submission_id=%s", (submission_id,))
            for c in result.get("checks", []):
                con.execute(
                    "insert into check_results (submission_id, check_code, check_name, result, "
                    "reason, evidence) values (%s,%s,%s,%s,%s,%s)",
                    (submission_id, c["check_code"], c.get("check_name", ""), c["result"],
                     c.get("reason", ""), json.dumps(c.get("evidence", {}))),
                )

    def create_approval(self, submission_id, decision, signed_by_name,
                        acknowledged_flags=None, bundle_path=None) -> Dict:
        approval_id = _new_id()
        with self._connect() as con:
            con.execute(
                "insert into approvals (id, submission_id, decision, signed_by_name, "
                "acknowledged_flags, bundle_path) values (%s,%s,%s,%s,%s,%s)",
                (approval_id, submission_id, decision, signed_by_name,
                 json.dumps(acknowledged_flags or []), bundle_path),
            )
            con.execute(
                "update submissions set status=%s where id=%s",
                ("released" if decision == "RELEASED" else "rejected", submission_id),
            )
        return {"id": approval_id, "submission_id": submission_id, "decision": decision,
                "signed_by_name": signed_by_name, "signed_at": _now()}

    def append_audit(self, action, submission_id=None, actor=None, detail=None) -> None:
        with self._connect() as con:
            con.execute(
                "insert into audit_log (submission_id, actor, action, detail) "
                "values (%s,%s,%s,%s)",
                (submission_id, actor, action, json.dumps(detail or {})),
            )


_store: Optional[LocalStore] = None


def get_store() -> LocalStore:
    global _store
    if _store is None:
        _store = PostgresStore() if settings().database_url else LocalStore()
    return _store
