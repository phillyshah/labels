"""Integration test for the editable rules config (GET/PUT /api/rules).

RULES_PATH is pointed at a temp file so the test never mutates the repo's config/rules.yaml.
"""

import importlib
import pathlib
import tempfile

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
EXAMPLE = REPO_ROOT / "config" / "rules.example.yaml"


@pytest.fixture()
def client(monkeypatch, tmp_path):
    rules_file = tmp_path / "rules.yaml"
    rules_file.write_text(EXAMPLE.read_text())  # start from the unconfigured example
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("LOCAL_DATA_DIR", tempfile.mkdtemp())
    monkeypatch.setenv("APP_PASSWORD", "testpw")
    monkeypatch.setenv("RULES_PATH", str(rules_file))
    from backend.app import config
    importlib.reload(config)
    from backend.app import main
    importlib.reload(main)
    from fastapi.testclient import TestClient
    return TestClient(main.app), rules_file


def _auth(c):
    tok = c.post("/api/login", json={"password": "testpw"}).json()["token"]
    return {"Authorization": f"Bearer {tok}"}


@pytest.mark.integration
def test_get_rules_returns_full_set(client):
    c, _ = client
    res = c.get("/api/rules", headers=_auth(c))
    assert res.status_code == 200
    body = res.json()
    assert body["gtin"]["configured"] is False
    assert "descriptions" in body and "static_content" in body


@pytest.mark.integration
def test_put_rules_activates_check_and_persists(client):
    c, rules_file = client
    h = _auth(c)
    payload = {
        "reviewer_name": "Tester",
        "rules": {
            "rules_version": "2026-06-25.configured",
            "gtin": {"configured": True, "ai240_hyphen": "optional",
                     "map": {"mtuux400-k": "10881176701838"}},  # lowercase -> normalized on save
            "descriptions": {"configured": True, "match_mode": "normalized",
                             "map": {"MTUUX400-K": "TIBIAL BASE PLATE / SIZE 4"}},
            "ifu": {"configured": False, "required_on_label": True},
            "static_content": {"configured": False, "families": {}, "ref_to_family": {}},
        },
    }
    res = c.put("/api/rules", headers=h, json=payload)
    assert res.status_code == 200, res.text
    saved = res.json()
    assert saved["gtin"]["configured"] is True
    # REF key normalized to uppercase so the engine lookup (which normalizes the REF) hits.
    assert saved["gtin"]["map"] == {"MTUUX400-K": "10881176701838"}

    # Persisted to disk and reloadable.
    on_disk = yaml.safe_load(rules_file.read_text())
    assert on_disk["rules_version"] == "2026-06-25.configured"
    assert on_disk["descriptions"]["configured"] is True

    # And reflected on a fresh GET.
    assert c.get("/api/rules", headers=h).json()["gtin"]["map"]["MTUUX400-K"] == "10881176701838"


@pytest.mark.integration
def test_put_rules_rejects_bad_gtin(client):
    c, _ = client
    h = _auth(c)
    res = c.put("/api/rules", headers=h, json={"rules": {
        "rules_version": "x",
        "gtin": {"configured": True, "ai240_hyphen": "optional", "map": {"REF1": "123"}},
    }})
    assert res.status_code == 400
    assert "14-digit" in res.json()["detail"]


@pytest.mark.integration
def test_put_rules_requires_version(client):
    c, _ = client
    res = c.put("/api/rules", headers=_auth(c), json={"rules": {"rules_version": ""}})
    assert res.status_code == 400
    assert "rules_version" in res.json()["detail"]
