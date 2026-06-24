"""FastAPI application: processor contract + reviewer API + static SPA hosting."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import (Depends, FastAPI, File, Form, HTTPException, Response,
                     UploadFile, status)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Make the repo-root `processor` package importable when running from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from processor import capabilities                      # noqa: E402
from processor.pipeline import process_submission        # noqa: E402

from . import auth, bundle                                # noqa: E402
from .config import rules, settings                       # noqa: E402
from .store import get_store                              # noqa: E402

app = FastAPI(title="Maxx Label Approval", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings().cors_origins.split(",")],
    allow_methods=["*"], allow_headers=["*"],
)

REQUIRED_DOCS = ("label_form", "batch_coc", "sterile_coc", "sterile_lot_record")
OPTIONAL_DOCS = ("doc_release_verification", "sterile_product_release_verification")


# --- health -----------------------------------------------------------------

@app.get("/healthz")
def healthz():
    caps = capabilities.probe()
    missing = capabilities.missing_required()
    db_error = get_store().healthcheck()  # actually probes Postgres when configured
    degraded = bool(missing) or bool(db_error)
    body = {"status": "ok" if not degraded else "degraded",
            "capabilities": caps, "rules_version": rules().get("rules_version"),
            "store": "postgres" if settings().database_url else "local"}
    if missing:
        body["missing_required"] = missing
    if db_error:
        body["db_error"] = db_error
    if degraded:
        return JSONResponse(body, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    return body


# --- processor contract (internal, shared-secret) ---------------------------

class ProcessRequest(BaseModel):
    submission_id: Optional[str] = None
    rules_version: Optional[str] = None
    documents: dict  # {type: {"path": "..."} or {"url": "..."}}


@app.post("/process", dependencies=[Depends(auth.require_processor_secret)])
def process(req: ProcessRequest):
    docs = {}
    for k, v in req.documents.items():
        path = v.get("path") if isinstance(v, dict) else v
        if path:
            docs[k] = path
    result = process_submission(docs, rules(), submission_id=req.submission_id)
    return result


# --- reviewer API -----------------------------------------------------------

class LoginRequest(BaseModel):
    password: str


@app.post("/api/login")
def api_login(req: LoginRequest):
    token = auth.login(req.password)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "incorrect password")
    return {"token": token, "role": "reviewer"}


async def _ingest(store, uploads: dict, is_training: bool):
    """Shared upload→persist→process path for both the live and training flows."""
    try:
        sid = store.create_submission(is_training=is_training)
        store.append_audit("UPLOAD", submission_id=sid, detail={"training": is_training})

        paths = {}
        for doc_type, upload in uploads.items():
            if upload is None:
                continue
            content = await upload.read()
            paths[doc_type] = store.save_input_file(
                sid, doc_type, upload.filename or "f.pdf", content)

        store.append_audit("RUN", submission_id=sid)
    except Exception as e:  # persistence/storage failure (e.g. bad DATABASE_URL)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"storage unavailable — check the database connection ({type(e).__name__})",
        )

    result = process_submission(paths, rules(), submission_id=sid)
    if result.get("error"):
        store.set_error(sid, result)
        return JSONResponse(result, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

    store.set_result(sid, result)
    store.append_audit("VERDICT", submission_id=sid, detail={"verdict": result["verdict"]})
    return result


@app.post("/api/submissions")
async def api_create_submission(
    _: dict = Depends(auth.current_reviewer),
    label_form: UploadFile = File(...),
    batch_coc: UploadFile = File(...),
    sterile_coc: UploadFile = File(...),
    sterile_lot_record: UploadFile = File(...),
    doc_release_verification: Optional[UploadFile] = File(None),
    sterile_product_release_verification: Optional[UploadFile] = File(None),
):
    uploads = {
        "label_form": label_form, "batch_coc": batch_coc,
        "sterile_coc": sterile_coc, "sterile_lot_record": sterile_lot_record,
        "doc_release_verification": doc_release_verification,
        "sterile_product_release_verification": sterile_product_release_verification,
    }
    return await _ingest(get_store(), uploads, is_training=False)


# --- training / feedback ----------------------------------------------------

@app.post("/api/training/submissions")
async def api_create_training_submission(
    _: dict = Depends(auth.current_reviewer),
    label_form: UploadFile = File(...),
    batch_coc: UploadFile = File(...),
    sterile_coc: UploadFile = File(...),
    sterile_lot_record: UploadFile = File(...),
    doc_release_verification: Optional[UploadFile] = File(None),
    sterile_product_release_verification: Optional[UploadFile] = File(None),
):
    uploads = {
        "label_form": label_form, "batch_coc": batch_coc,
        "sterile_coc": sterile_coc, "sterile_lot_record": sterile_lot_record,
        "doc_release_verification": doc_release_verification,
        "sterile_product_release_verification": sterile_product_release_verification,
    }
    return await _ingest(get_store(), uploads, is_training=True)


@app.get("/api/training/submissions")
def api_list_training(_: dict = Depends(auth.current_reviewer)):
    rows = get_store().list_submissions(training=True)
    return [{k: v for k, v in r.items() if k != "_result"} for r in rows]


@app.get("/api/training/metrics")
def api_training_metrics(_: dict = Depends(auth.current_reviewer)):
    return get_store().training_metrics()


class FeedbackItem(BaseModel):
    target: str                         # 'A'..'G', 'verdict', or a field name
    rating: str                         # correct | partial | wrong
    expected: Optional[str] = None
    note: Optional[str] = None


class FeedbackRequest(BaseModel):
    reviewer_name: Optional[str] = None
    items: List[FeedbackItem]


@app.post("/api/submissions/{submission_id}/feedback")
def api_add_feedback(submission_id: str, req: FeedbackRequest,
                     _: dict = Depends(auth.current_reviewer)):
    store = get_store()
    if not store.get_submission(submission_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "submission not found")
    valid = {"correct", "partial", "wrong"}
    bad = [it.target for it in req.items if it.rating not in valid]
    if bad:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "rating must be one of correct/partial/wrong")
    n = store.add_feedback(
        submission_id,
        [it.model_dump() for it in req.items],
        by_name=(req.reviewer_name or "").strip() or None)
    store.append_audit("FEEDBACK", submission_id=submission_id,
                       actor=req.reviewer_name, detail={"count": n})
    return {"saved": n}


@app.get("/api/submissions/{submission_id}/feedback")
def api_get_feedback(submission_id: str, _: dict = Depends(auth.current_reviewer)):
    return get_store().get_feedback(submission_id)


@app.get("/api/submissions")
def api_list(_: dict = Depends(auth.current_reviewer)):
    rows = get_store().list_submissions()
    return [{k: v for k, v in r.items() if k != "_result"} for r in rows]


@app.get("/api/submissions/{submission_id}")
def api_get(submission_id: str, _: dict = Depends(auth.current_reviewer)):
    sub = get_store().get_submission(submission_id)
    if not sub:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "submission not found")
    return sub.get("_result") or {k: v for k, v in sub.items() if k != "_result"}


class SignRequest(BaseModel):
    decision: str                       # RELEASED | REJECTED
    signer_name: str
    acknowledged_flags: List[dict] = []


@app.post("/api/submissions/{submission_id}/sign")
def api_sign(submission_id: str, req: SignRequest,
             _: dict = Depends(auth.current_reviewer)):
    if req.decision not in ("RELEASED", "REJECTED"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "decision must be RELEASED or REJECTED")
    if not req.signer_name.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "signer_name required")

    store = get_store()
    sub = store.get_submission(submission_id)
    if not sub:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "submission not found")
    result = sub.get("_result") or {}

    out_dir = Path(settings().local_data_dir) / "uploads" / submission_id / "outputs"
    bundle_path = bundle.generate_bundle(
        str(out_dir / ("approval_bundle.pdf" if req.decision == "RELEASED"
                       else "discrepancy_report.pdf")),
        result, req.decision, req.signer_name, req.acknowledged_flags,
    )
    try:
        approval = store.create_approval(
            submission_id, req.decision, req.signer_name.strip(),
            acknowledged_flags=req.acknowledged_flags, bundle_path=bundle_path)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    store.append_audit("SIGN" if req.decision == "RELEASED" else "REJECT",
                       submission_id=submission_id, actor=req.signer_name,
                       detail={"decision": req.decision})
    return {"approval": approval, "bundle_available": bundle_path is not None}


@app.get("/api/submissions/{submission_id}/bundle")
def api_bundle(submission_id: str, _: dict = Depends(auth.current_reviewer)):
    store = get_store()
    approval = store.get_approval(submission_id)
    if not approval or not approval.get("bundle_path") or not Path(approval["bundle_path"]).exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "bundle not available")
    sub = store.get_submission(submission_id) or {}

    def _safe(v: object) -> str:
        s = "".join(c if (c.isalnum() or c in "._-") else "-" for c in str(v or "NA"))
        return s.strip("-") or "NA"

    fname = (f"Maxx-LabelReview_{_safe(sub.get('ref'))}_{_safe(sub.get('lot'))}"
             f"_{_safe(approval.get('decision'))}.pdf")
    return FileResponse(approval["bundle_path"], media_type="application/pdf", filename=fname)


# --- static SPA hosting (built frontend) ------------------------------------
# In production the Vite build is copied to backend/static and served here behind Traefik.
_static_dir = Path(__file__).resolve().parents[1] / "static"
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="spa")
