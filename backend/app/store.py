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


def _disagreement_row(f: Dict, ref, lot, result: Dict) -> Dict:
    """One disagreement enriched with the tool's output for the rated target."""
    target = f.get("target")
    if target == "verdict":
        tool_result, tool_reason = result.get("verdict"), ""
    else:
        chk = next((c for c in result.get("checks", [])
                    if c.get("check_code") == target), {})
        tool_result, tool_reason = chk.get("result"), chk.get("reason", "")
    return {"ref": ref, "lot": lot, "target": target,
            "tool_result": tool_result, "tool_reason": tool_reason,
            "rating": f.get("rating"), "expected": f.get("expected"), "note": f.get("note")}


def _summarize_metrics(feedback: List[Dict], batches: int) -> Dict:
    """Accuracy dashboard from the feedback corpus. correct=1, partial=0.5, wrong=0."""
    weight = {"correct": 1.0, "partial": 0.5, "wrong": 0.0}

    def bucket():
        return {"correct": 0, "partial": 0, "wrong": 0}

    overall = bucket()
    by_target: Dict[str, Dict] = {}
    for f in feedback:
        r = f.get("rating")
        if r not in weight:
            continue
        overall[r] += 1
        t = f.get("target") or "?"
        by_target.setdefault(t, bucket())[r] += 1

    def acc(b: Dict) -> Optional[float]:
        n = b["correct"] + b["partial"] + b["wrong"]
        if not n:
            return None
        return round((b["correct"] * weight["correct"] + b["partial"] * weight["partial"]) / n, 4)

    return {
        "batches": batches,
        "feedback_count": len(feedback),
        "overall": {**overall, "accuracy": acc(overall)},
        "by_target": {t: {**b, "accuracy": acc(b)} for t, b in sorted(by_target.items())},
    }


class LocalStore:
    """Filesystem-backed store for development (no Supabase required)."""

    def __init__(self, root: Optional[str] = None):
        self.root = Path(root or settings().local_data_dir)
        (self.root / "uploads").mkdir(parents=True, exist_ok=True)
        self._db = self.root / "db.json"
        if not self._db.exists():
            self._write({"submissions": {}, "check_results": [], "approvals": {},
                         "audit_log": [], "feedback": []})

    # --- internals ---
    def _read(self) -> Dict:
        data = json.loads(self._db.read_text())
        data.setdefault("feedback", [])  # backfill for dbs created before training existed
        return data

    def _write(self, data: Dict) -> None:
        self._db.write_text(json.dumps(data, indent=2, default=str))

    # --- submissions ---
    def create_submission(self, identity: Optional[Dict] = None,
                          is_training: bool = False) -> str:
        sid = _new_id()
        data = self._read()
        data["submissions"][sid] = {
            "id": sid, "created_at": _now(), "status": "uploaded",
            "verdict": None, "rules_version": None, "processor_ms": None,
            "ref": (identity or {}).get("ref"), "lot": (identity or {}).get("lot"),
            "sterile_lot": (identity or {}).get("sterile_lot"), "error_detail": None,
            "is_training": is_training,
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

    def list_submissions(self, training: Optional[bool] = False) -> List[Dict]:
        subs = list(self._read()["submissions"].values())
        if training is not None:
            subs = [s for s in subs if bool(s.get("is_training")) == training]
        return sorted(subs, key=lambda s: s["created_at"], reverse=True)

    # --- feedback (training corpus) ---
    def add_feedback(self, submission_id: str, items: List[Dict],
                     by_name: Optional[str] = None) -> int:
        data = self._read()
        n = 0
        for it in items:
            data["feedback"].append({
                "id": _new_id(), "submission_id": submission_id,
                "target": it.get("target"), "rating": it.get("rating"),
                "expected": it.get("expected"), "note": it.get("note"),
                "created_by_name": by_name, "created_at": _now(),
            })
            n += 1
        self._write(data)
        return n

    def get_feedback(self, submission_id: str) -> List[Dict]:
        return [f for f in self._read().get("feedback", [])
                if f.get("submission_id") == submission_id]

    def training_metrics(self) -> Dict:
        data = self._read()
        fb = data.get("feedback", [])
        training_subs = [s for s in data["submissions"].values() if s.get("is_training")]
        return _summarize_metrics(fb, len(training_subs))

    def disagreement_corpus(self) -> List[Dict]:
        """Feedback rows where the reviewer disagreed (rating != correct), enriched with the
        tool's own output for that target — the input the AI-assist step reasons over."""
        data = self._read()
        subs = data["submissions"]
        out = []
        for f in data.get("feedback", []):
            if f.get("rating") == "correct":
                continue
            sub = subs.get(f.get("submission_id")) or {}
            out.append(_disagreement_row(f, sub.get("ref"), sub.get("lot"),
                                         sub.get("_result") or {}))
        return out

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

    def healthcheck(self) -> Optional[str]:
        """Return None if the store is usable, else a short error string. Local store is always ok."""
        return None


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

    def healthcheck(self) -> Optional[str]:
        """Probe the actual Postgres connection so a bad DATABASE_URL surfaces at /healthz
        rather than as a 500 on the first upload."""
        try:
            with self._connect() as con:
                con.execute("select 1")
            return None
        except Exception as e:  # connection refused / auth / bad host etc.
            return f"{type(e).__name__}: {str(e).splitlines()[0][:200]}"

    def create_submission(self, identity: Optional[Dict] = None,
                          is_training: bool = False) -> str:
        sid = _new_id()
        with self._connect() as con:
            con.execute(
                "insert into submissions (id, ref, lot, sterile_lot, status, is_training) "
                "values (%s,%s,%s,%s,'uploaded',%s)",
                (sid, (identity or {}).get("ref"), (identity or {}).get("lot"),
                 (identity or {}).get("sterile_lot"), is_training),
            )
        return sid

    def set_result(self, submission_id: str, result: Dict) -> None:
        ident = result.get("identity", {})
        with self._connect() as con:
            con.execute(
                "update submissions set status='reviewed', verdict=%s, rules_version=%s, "
                "processor_ms=%s, ref=%s, lot=%s, sterile_lot=%s, result_json=%s where id=%s",
                (result.get("verdict"), result.get("rules_version"), result.get("processor_ms"),
                 ident.get("ref"), ident.get("lot"), ident.get("sterile_lot"),
                 json.dumps(result), submission_id),
            )
            con.execute("delete from check_results where submission_id=%s", (submission_id,))
            for c in result.get("checks", []):
                con.execute(
                    "insert into check_results (submission_id, check_code, check_name, result, "
                    "reason, evidence) values (%s,%s,%s,%s,%s,%s)",
                    (submission_id, c["check_code"], c.get("check_name", ""), c["result"],
                     c.get("reason", ""), json.dumps(c.get("evidence", {}))),
                )

    def set_error(self, submission_id: str, error: Dict) -> None:
        # Parent writes to the JSON file (which has no PG row); persist to Postgres instead.
        with self._connect() as con:
            con.execute(
                "update submissions set status='error', error_detail=%s, result_json=%s where id=%s",
                (error.get("detail"), json.dumps(error), submission_id),
            )

    def create_approval(self, submission_id, decision, signed_by_name,
                        acknowledged_flags=None, bundle_path=None) -> Dict:
        import psycopg
        approval_id = _new_id()
        try:
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
        except psycopg.errors.UniqueViolation:
            # An approval already exists for this submission — the sign is immutable.
            raise ValueError("approval already exists for this submission (immutable)")
        return {"id": approval_id, "submission_id": submission_id, "decision": decision,
                "signed_by_name": signed_by_name, "signed_at": _now()}

    def append_audit(self, action, submission_id=None, actor=None, detail=None) -> None:
        with self._connect() as con:
            con.execute(
                "insert into audit_log (submission_id, action, detail) "
                "values (%s,%s,%s)",
                (submission_id, action, json.dumps((detail or {}) | (
                    {"actor": actor} if actor else {}))),
            )

    # --- reads (must hit Postgres too; the parent's JSON-file reads never see PG rows) ---
    def get_submission(self, submission_id: str) -> Optional[Dict]:
        with self._connect() as con:
            cur = con.execute(
                "select id, created_at, status, verdict, rules_version, processor_ms, "
                "ref, lot, sterile_lot, error_detail, result_json from submissions where id=%s",
                (submission_id,))
            row = cur.fetchone()
            if not row:
                return None
            cols = [d.name for d in cur.description]
            sub = dict(zip(cols, row))
        # Prefer the full stored result so the scorecard + signed bundle get the source-of-truth
        # table, full identity and per-check evidence verbatim (psycopg returns jsonb as a dict).
        stored = sub.pop("result_json", None)
        if stored:
            sub["_result"] = stored
        return sub

    def list_submissions(self, training: Optional[bool] = False) -> List[Dict]:
        where = "" if training is None else "where coalesce(is_training,false)=%s "
        params = () if training is None else (training,)
        with self._connect() as con:
            cur = con.execute(
                "select id, created_at, status, verdict, ref, lot, sterile_lot "
                f"from submissions {where}order by created_at desc", params)
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def add_feedback(self, submission_id: str, items: List[Dict],
                     by_name: Optional[str] = None) -> int:
        n = 0
        with self._connect() as con:
            for it in items:
                con.execute(
                    "insert into feedback (submission_id, target, rating, expected, note, "
                    "created_by_name) values (%s,%s,%s,%s,%s,%s)",
                    (submission_id, it.get("target"), it.get("rating"),
                     it.get("expected"), it.get("note"), by_name))
                n += 1
        return n

    def get_feedback(self, submission_id: str) -> List[Dict]:
        with self._connect() as con:
            cur = con.execute(
                "select id, submission_id, target, rating, expected, note, created_by_name, "
                "created_at from feedback where submission_id=%s order by created_at", (submission_id,))
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def training_metrics(self) -> Dict:
        with self._connect() as con:
            cur = con.execute("select target, rating from feedback")
            fb = [{"target": t, "rating": r} for t, r in cur.fetchall()]
            cur = con.execute("select count(*) from submissions where coalesce(is_training,false)=true")
            batches = cur.fetchone()[0]
        return _summarize_metrics(fb, batches)

    def disagreement_corpus(self) -> List[Dict]:
        with self._connect() as con:
            cur = con.execute(
                "select f.target, f.rating, f.expected, f.note, s.ref, s.lot, s.result_json "
                "from feedback f join submissions s on s.id = f.submission_id "
                "where f.rating <> 'correct' order by f.created_at")
            rows = cur.fetchall()
        out = []
        for target, rating, expected, note, ref, lot, result_json in rows:
            f = {"target": target, "rating": rating, "expected": expected, "note": note}
            out.append(_disagreement_row(f, ref, lot, result_json or {}))
        return out

    def get_approval(self, submission_id: str) -> Optional[Dict]:
        with self._connect() as con:
            cur = con.execute(
                "select id, submission_id, decision, signed_by_name, signed_at, "
                "acknowledged_flags, bundle_path from approvals where submission_id=%s",
                (submission_id,))
            row = cur.fetchone()
            if not row:
                return None
            cols = [d.name for d in cur.description]
            return dict(zip(cols, row))


_store: Optional[LocalStore] = None


def get_store() -> LocalStore:
    global _store
    if _store is None:
        _store = PostgresStore() if settings().database_url else LocalStore()
    return _store
