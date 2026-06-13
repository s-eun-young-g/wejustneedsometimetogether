"""Backend API tests via FastAPI's TestClient. Skipped if FastAPI isn't installed."""

from datetime import datetime, timedelta

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlmodel")

from fastapi.testclient import TestClient

from tt.server.app import create_app

BASE = datetime(2026, 6, 1, 9, 0)


@pytest.fixture
def client():
    return TestClient(create_app("sqlite://"))      # fresh in-memory db


def register(client, name):
    r = client.post("/auth/register", json={"name": name})
    assert r.status_code == 200
    d = r.json()
    return d["user_id"], {"Authorization": f"Bearer {d['token']}"}


def test_register_and_me(client):
    uid, auth = register(client, "you")
    me = client.get("/me", headers=auth).json()
    assert me == {"user_id": uid, "name": "you"}


def test_me_requires_token(client):
    assert client.get("/me").status_code == 401
    assert client.get("/me", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_group_create_and_join(client):
    _, you = register(client, "you")
    _, alex = register(client, "alex")
    code = client.post("/groups", json={"name": "Crew"}, headers=you).json()["invite_code"]
    client.post("/groups/join", json={"invite_code": code}, headers=alex)
    groups = client.get("/groups", headers=you).json()
    assert len(groups) == 1
    assert {m["name"] for m in groups[0]["members"]} == {"you", "alex"}


def test_ingest_requires_shared_group(client):
    you_id, you = register(client, "you")
    alex_id, alex = register(client, "alex")
    # not in a group together yet → ingest is rejected (0 ingested)
    body = {"sessions": [{"peer_id": alex_id, "start": BASE.isoformat(),
                          "end": (BASE + timedelta(minutes=40)).isoformat(),
                          "place": "Java House"}]}
    assert client.post("/sessions", json=body, headers=you).json()["ingested"] == 0
    # join a shared group → now allowed
    code = client.post("/groups", json={"name": "Crew"}, headers=you).json()["invite_code"]
    client.post("/groups/join", json={"invite_code": code}, headers=alex)
    assert client.post("/sessions", json=body, headers=you).json()["ingested"] == 1


def _setup_hangs(client):
    you_id, you = register(client, "you")
    alex_id, alex = register(client, "alex")
    code = client.post("/groups", json={"name": "Crew"}, headers=you).json()["invite_code"]
    client.post("/groups/join", json={"invite_code": code}, headers=alex)
    sessions = []
    for day in range(3):                     # 3 daily coffees with alex
        s = BASE + timedelta(days=day)
        sessions.append({"peer_id": alex_id, "start": s.isoformat(),
                         "end": (s + timedelta(minutes=40)).isoformat(),
                         "place": "Java House"})
    client.post("/sessions", json={"sessions": sessions}, headers=you)
    return you, alex


def test_wrapped_endpoint(client):
    you, _ = _setup_hangs(client)
    r = client.get("/wrapped", headers=you)
    assert r.status_code == 200
    data = r.json()
    assert data["me"] == "you"
    assert data["top_person"] == "alex"
    assert data["total_minutes"] == 120        # 3 × 40 min
    assert data["third_place"] == "Java House"


def test_wrapped_reconciles_duplicate_uploads(client):
    """Both phones upload the same hang → it should count once, not twice."""
    you, alex = _setup_hangs(client)
    # alex re-uploads the same first coffee (overlapping) from their side
    s = BASE
    dup = {"sessions": [{"peer_id": _me_id(client, you), "start": s.isoformat(),
                         "end": (s + timedelta(minutes=40)).isoformat(),
                         "place": "Java House"}]}
    client.post("/sessions", json=dup, headers=alex)
    data = client.get("/wrapped", headers=you).json()
    assert data["total_minutes"] == 120        # still 120, duplicate merged away


def _me_id(client, auth):
    return client.get("/me", headers=auth).json()["user_id"]
