"""Tests for GET /api/boards/{id}/stats and GET /api/boards/{id}/activity."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


def register_and_login(client, username, password="Str0ngPass!"):
    client.post("/api/auth/register", json={"username": username, "password": password})
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def make_board_with_cards():
    return {
        "columns": [
            {"id": "col-todo", "title": "Todo", "cardIds": ["card-1", "card-2"]},
            {"id": "col-done", "title": "Done", "cardIds": ["card-3"]},
        ],
        "cards": {
            "card-1": {"id": "card-1", "title": "T1", "details": "", "priority": "high", "due_date": "2020-01-01"},
            "card-2": {"id": "card-2", "title": "T2", "details": "", "priority": "low"},
            "card-3": {"id": "card-3", "title": "T3", "details": "", "priority": "high"},
        },
    }


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def test_stats_total_cards(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    board = make_board_with_cards()
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        client.put(f"/api/boards/{board_id}", json=board, headers=headers)
        resp = client.get(f"/api/boards/{board_id}/stats", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_cards"] == 3


def test_stats_column_counts(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    board = make_board_with_cards()
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        client.put(f"/api/boards/{board_id}", json=board, headers=headers)
        resp = client.get(f"/api/boards/{board_id}/stats", headers=headers)
    cols = {c["column_title"]: c["card_count"] for c in resp.json()["columns"]}
    assert cols["Todo"] == 2
    assert cols["Done"] == 1


def test_stats_priority_breakdown(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    board = make_board_with_cards()
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        client.put(f"/api/boards/{board_id}", json=board, headers=headers)
        resp = client.get(f"/api/boards/{board_id}/stats", headers=headers)
    pb = resp.json()["priority_breakdown"]
    assert pb["high"] == 2
    assert pb["low"] == 1
    assert pb["medium"] == 0


def test_stats_overdue_count(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    board = make_board_with_cards()  # card-1 has due_date=2020-01-01 (past)
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        client.put(f"/api/boards/{board_id}", json=board, headers=headers)
        resp = client.get(f"/api/boards/{board_id}/stats", headers=headers)
    assert resp.json()["overdue_count"] == 1


def test_stats_requires_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        resp = client.get("/api/boards/fake-id/stats")
    assert resp.status_code == 401


def test_stats_wrong_owner_forbidden(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers_a = register_and_login(client, "alice")
        headers_b = register_and_login(client, "bob")
        board_id = client.post("/api/boards", json={"title": "Alice's"}, headers=headers_a).json()["id"]
        resp = client.get(f"/api/boards/{board_id}/stats", headers=headers_b)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Activity
# ---------------------------------------------------------------------------

def test_activity_empty_initially(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        resp = client.get(f"/api/boards/{board_id}/activity", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["entries"] == []


def test_activity_logged_after_board_save(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    board = make_board_with_cards()
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        client.put(f"/api/boards/{board_id}", json=board, headers=headers)
        resp = client.get(f"/api/boards/{board_id}/activity", headers=headers)
    entries = resp.json()["entries"]
    assert len(entries) >= 1
    assert entries[0]["action"] == "board_updated"


def test_activity_logged_after_rename(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "Old"}, headers=headers).json()["id"]
        client.patch(f"/api/boards/{board_id}", json={"title": "New"}, headers=headers)
        resp = client.get(f"/api/boards/{board_id}/activity", headers=headers)
    entries = resp.json()["entries"]
    assert any(e["action"] == "board_renamed" for e in entries)


def test_activity_multiple_saves_accumulate(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    board = {"columns": [{"id": "col-a", "title": "A", "cardIds": []}], "cards": {}}
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        client.put(f"/api/boards/{board_id}", json=board, headers=headers)
        client.put(f"/api/boards/{board_id}", json=board, headers=headers)
        client.put(f"/api/boards/{board_id}", json=board, headers=headers)
        resp = client.get(f"/api/boards/{board_id}/activity", headers=headers)
    assert len(resp.json()["entries"]) == 3


def test_activity_requires_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        resp = client.get("/api/boards/fake-id/activity")
    assert resp.status_code == 401


def test_activity_wrong_owner_forbidden(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers_a = register_and_login(client, "alice")
        headers_b = register_and_login(client, "bob")
        board_id = client.post("/api/boards", json={"title": "Alice's"}, headers=headers_a).json()["id"]
        resp = client.get(f"/api/boards/{board_id}/activity", headers=headers_b)
    assert resp.status_code == 403
