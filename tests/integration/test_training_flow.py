"""Integration test for the training/feedback flow through the real FastAPI app.

Uses LocalStore (no DATABASE_URL) against the bundled sample PDFs: upload a training batch,
confirm it stays out of the live history, post per-check feedback, and read the accuracy metrics.
"""

import importlib
import os
import pathlib
import tempfile

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SAMPLES = REPO_ROOT / "reference-documents" / "samples"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("LOCAL_DATA_DIR", tempfile.mkdtemp())
    monkeypatch.setenv("APP_PASSWORD", "testpw")
    from backend.app import config
    importlib.reload(config)
    from backend.app import main
    importlib.reload(main)
    from fastapi.testclient import TestClient
    return TestClient(main.app)


def _auth(client):
    tok = client.post("/api/login", json={"password": "testpw"}).json()["token"]
    return {"Authorization": f"Bearer {tok}"}


def _sample_files():
    return {
        "label_form": open(SAMPLES / "1__V11022719_label.pdf", "rb"),
        "batch_coc": open(SAMPLES / "1__V11022719_COC.pdf", "rb"),
        "sterile_coc": open(SAMPLES / "M26-179_COC.pdf", "rb"),
        "sterile_lot_record": open(SAMPLES / "Sterile_Lot_Record_M26-179.pdf", "rb"),
    }


@pytest.mark.integration
def test_training_upload_feedback_and_metrics(client):
    h = _auth(client)

    res = client.post("/api/training/submissions", headers=h, files=_sample_files())
    assert res.status_code == 200, res.text
    sid = res.json()["submission_id"]

    # The training batch must not leak into the live history, but must appear in the training list.
    assert all(r["id"] != sid for r in client.get("/api/submissions", headers=h).json())
    assert any(r["id"] == sid for r in client.get("/api/training/submissions", headers=h).json())

    # Post per-check feedback.
    fb = client.post(f"/api/submissions/{sid}/feedback", headers=h, json={
        "reviewer_name": "Tester",
        "items": [
            {"target": "A", "rating": "correct"},
            {"target": "C", "rating": "wrong", "expected": "PASS", "note": "AI(240) hyphen ok"},
            {"target": "verdict", "rating": "correct"},
        ],
    })
    assert fb.status_code == 200 and fb.json()["saved"] == 3

    metrics = client.get("/api/training/metrics", headers=h).json()
    assert metrics["batches"] == 1
    assert metrics["feedback_count"] == 3
    assert metrics["by_target"]["A"]["accuracy"] == 1.0
    assert metrics["by_target"]["C"]["accuracy"] == 0.0
    assert 0.0 <= metrics["overall"]["accuracy"] <= 1.0


@pytest.mark.integration
def test_invalid_rating_rejected(client):
    h = _auth(client)
    sid = client.post("/api/training/submissions", headers=h,
                      files=_sample_files()).json()["submission_id"]
    bad = client.post(f"/api/submissions/{sid}/feedback", headers=h,
                      json={"items": [{"target": "A", "rating": "great"}]})
    assert bad.status_code == 400
