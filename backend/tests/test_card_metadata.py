"""Tests for card priority, due_date, labels, and user profile endpoints."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


def register_and_login(client, username, password="Str0ngPass!"):
    client.post("/api/auth/register", json={"username": username, "password": password})
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def make_board(cards=None):
    cards = cards or {"card-1": {"id": "card-1", "title": "Task", "details": ""}}
    return {
        "columns": [{"id": "col-a", "title": "Todo", "cardIds": list(cards.keys())}],
        "cards": cards,
    }


# ---------------------------------------------------------------------------
# Card priority
# ---------------------------------------------------------------------------

def test_card_with_priority_round_trips(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    board = make_board({"card-1": {"id": "card-1", "title": "Urgent task", "details": "", "priority": "urgent"}})
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        client.put(f"/api/boards/{board_id}", json=board, headers=headers)
        data = client.get(f"/api/boards/{board_id}", headers=headers).json()
    assert data["cards"]["card-1"]["priority"] == "urgent"


def test_card_priority_all_values_valid(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        for i, priority in enumerate(("low", "medium", "high", "urgent")):
            card_id = f"card-{i}"
            col_id = f"col-{i}"
            board = {
                "columns": [{"id": col_id, "title": "Todo", "cardIds": [card_id]}],
                "cards": {card_id: {"id": card_id, "title": "T", "details": "", "priority": priority}},
            }
            board_id = client.post("/api/boards", json={"title": f"B-{priority}"}, headers=headers).json()["id"]
            resp = client.put(f"/api/boards/{board_id}", json=board, headers=headers)
            assert resp.status_code == 200, f"Priority '{priority}' should be valid"


def test_card_invalid_priority_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    board = make_board({"card-1": {"id": "card-1", "title": "T", "details": "", "priority": "critical"}})
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        resp = client.put(f"/api/boards/{board_id}", json=board, headers=headers)
    assert resp.status_code == 422


def test_card_no_priority_defaults_null(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    board = make_board({"card-1": {"id": "card-1", "title": "T", "details": ""}})
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        client.put(f"/api/boards/{board_id}", json=board, headers=headers)
        data = client.get(f"/api/boards/{board_id}", headers=headers).json()
    assert data["cards"]["card-1"]["priority"] is None


# ---------------------------------------------------------------------------
# Card due_date
# ---------------------------------------------------------------------------

def test_card_due_date_round_trips(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    board = make_board({"card-1": {"id": "card-1", "title": "T", "details": "", "due_date": "2026-12-31"}})
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        client.put(f"/api/boards/{board_id}", json=board, headers=headers)
        data = client.get(f"/api/boards/{board_id}", headers=headers).json()
    assert data["cards"]["card-1"]["due_date"] == "2026-12-31"


def test_card_invalid_due_date_format_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    board = make_board({"card-1": {"id": "card-1", "title": "T", "details": "", "due_date": "31-12-2026"}})
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        resp = client.put(f"/api/boards/{board_id}", json=board, headers=headers)
    assert resp.status_code == 422


def test_card_null_due_date_stored_as_none(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    board = make_board({"card-1": {"id": "card-1", "title": "T", "details": "", "due_date": None}})
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        client.put(f"/api/boards/{board_id}", json=board, headers=headers)
        data = client.get(f"/api/boards/{board_id}", headers=headers).json()
    assert data["cards"]["card-1"]["due_date"] is None


# ---------------------------------------------------------------------------
# Card labels
# ---------------------------------------------------------------------------

def test_card_labels_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    board = make_board({"card-1": {"id": "card-1", "title": "T", "details": "", "labels": ["bug", "frontend"]}})
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        client.put(f"/api/boards/{board_id}", json=board, headers=headers)
        data = client.get(f"/api/boards/{board_id}", headers=headers).json()
    assert data["cards"]["card-1"]["labels"] == ["bug", "frontend"]


def test_card_empty_labels_default(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    board = make_board({"card-1": {"id": "card-1", "title": "T", "details": ""}})
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        client.put(f"/api/boards/{board_id}", json=board, headers=headers)
        data = client.get(f"/api/boards/{board_id}", headers=headers).json()
    assert data["cards"]["card-1"]["labels"] == []


def test_card_full_metadata_persists(tmp_path, monkeypatch):
    """All metadata fields survive a round-trip together."""
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    card = {
        "id": "card-1", "title": "Full card", "details": "details",
        "priority": "high", "due_date": "2026-06-01", "labels": ["v2", "infra"],
    }
    board = make_board({"card-1": card})
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        client.put(f"/api/boards/{board_id}", json=board, headers=headers)
        data = client.get(f"/api/boards/{board_id}", headers=headers).json()
    c = data["cards"]["card-1"]
    assert c["priority"] == "high"
    assert c["due_date"] == "2026-06-01"
    assert c["labels"] == ["v2", "infra"]


# ---------------------------------------------------------------------------
# User profile (GET /api/me)
# ---------------------------------------------------------------------------

def test_get_profile_returns_username(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        resp = client.get("/api/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "alice"


def test_get_profile_board_count(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        client.post("/api/boards", json={"title": "Board A"}, headers=headers)
        client.post("/api/boards", json={"title": "Board B"}, headers=headers)
        resp = client.get("/api/me", headers=headers)
    assert resp.json()["board_count"] == 2


def test_get_profile_requires_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        resp = client.get("/api/me")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Change password (PATCH /api/me/password)
# ---------------------------------------------------------------------------

def test_change_password_success(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice", "OldPass123!")
        resp = client.patch(
            "/api/me/password",
            json={"current_password": "OldPass123!", "new_password": "NewPass456!"},
            headers=headers,
        )
        assert resp.status_code == 204
        # old password no longer works
        old_login = client.post("/api/auth/login", json={"username": "alice", "password": "OldPass123!"})
        new_login = client.post("/api/auth/login", json={"username": "alice", "password": "NewPass456!"})
    assert old_login.status_code == 401
    assert new_login.status_code == 200


def test_change_password_wrong_current(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice", "OldPass123!")
        resp = client.patch(
            "/api/me/password",
            json={"current_password": "wrongpass", "new_password": "NewPass456!"},
            headers=headers,
        )
    assert resp.status_code == 401


def test_change_password_new_too_short(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice", "OldPass123!")
        resp = client.patch(
            "/api/me/password",
            json={"current_password": "OldPass123!", "new_password": "short"},
            headers=headers,
        )
    assert resp.status_code == 422


def test_change_password_requires_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        resp = client.patch(
            "/api/me/password",
            json={"current_password": "old", "new_password": "NewPass456!"},
        )
    assert resp.status_code == 401
