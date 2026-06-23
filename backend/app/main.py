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
    body = {"status": "ok" if not missing else "degraded",
            "capabilities": caps, "rules_version": rules().get("rules_version"),
            "store": "postgres" if settings().database_url else "local"}
    if missing:
        return JSONResponse(body | {"missing_required": missing},
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
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
    store = get_store()
    sid = store.create_submission()
    store.append_audit("UPLOAD", submission_id=sid)

    uploads = {
        "label_form": label_form, "batch_coc": batch_coc,
        "sterile_coc": sterile_coc, "sterile_lot_record": sterile_lot_record,
        "doc_release_verification": doc_release_verification,
        "sterile_product_release_verification": sterile_product_release_verification,
    }
    paths = {}
    for doc_type, upload in uploads.items():
        if upload is None:
            continue
        content = await upload.read()
        paths[doc_type] = store.save_input_file(sid, doc_type, upload.filename or "f.pdf", content)

    store.append_audit("RUN", submission_id=sid)
    result = process_submission(paths, rules(), submission_id=sid)
    if result.get("error"):
        store.set_error(sid, result)
        return JSONResponse(result, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

    store.set_result(sid, result)
    store.append_audit("VERDICT", submission_id=sid, detail={"verdict": result["verdict"]})
    return result


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
    approval = get_store().get_approval(submission_id)
    if not approval or not approval.get("bundle_path") or not Path(approval["bundle_path"]).exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "bundle not available")
    return FileResponse(approval["bundle_path"], media_type="application/pdf",
                        filename=f"{submission_id}.pdf")


# --- static SPA hosting (built frontend) ------------------------------------
# In production the Vite build is copied to backend/static and served here behind Traefik.
_static_dir = Path(__file__).resolve().parents[1] / "static"
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="spa")
