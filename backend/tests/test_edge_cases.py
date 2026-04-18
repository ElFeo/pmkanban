"""Edge case and input validation tests."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


def register_and_login(client, username, password="Str0ngPass!"):
    client.post("/api/auth/register", json={"username": username, "password": password})
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Registration validation
# ---------------------------------------------------------------------------

def test_register_username_too_short(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        resp = client.post("/api/auth/register", json={"username": "ab", "password": "Str0ngPass!"})
    assert resp.status_code == 422


def test_register_username_invalid_chars(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        resp = client.post("/api/auth/register", json={"username": "bad user!", "password": "Str0ngPass!"})
    assert resp.status_code == 422


def test_register_password_too_short(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        resp = client.post("/api/auth/register", json={"username": "alice", "password": "short"})
    assert resp.status_code == 422


def test_register_duplicate_username(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        client.post("/api/auth/register", json={"username": "alice", "password": "Str0ngPass!"})
        resp = client.post("/api/auth/register", json={"username": "alice", "password": "Str0ngPass!"})
    assert resp.status_code == 409


def test_register_and_login_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        reg = client.post("/api/auth/register", json={"username": "newuser", "password": "Str0ngPass!"})
        assert reg.status_code == 201
        login = client.post("/api/auth/login", json={"username": "newuser", "password": "Str0ngPass!"})
        assert login.status_code == 200
        assert "access_token" in login.json()


# ---------------------------------------------------------------------------
# Board title validation
# ---------------------------------------------------------------------------

def test_create_board_empty_title_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        resp = client.post("/api/boards", json={"title": ""}, headers=headers)
    assert resp.status_code == 422


def test_create_board_title_too_long_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        resp = client.post("/api/boards", json={"title": "x" * 101}, headers=headers)
    assert resp.status_code == 422


def test_rename_board_empty_title_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        resp = client.patch(f"/api/boards/{board_id}", json={"title": ""}, headers=headers)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Card field validation
# ---------------------------------------------------------------------------

def test_card_title_empty_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    board = {
        "columns": [{"id": "col-a", "title": "T", "cardIds": ["c1"]}],
        "cards": {"c1": {"id": "c1", "title": "", "details": ""}},
    }
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        resp = client.put(f"/api/boards/{board_id}", json=board, headers=headers)
    assert resp.status_code == 422


def test_card_details_too_long_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    board = {
        "columns": [{"id": "col-a", "title": "T", "cardIds": ["c1"]}],
        "cards": {"c1": {"id": "c1", "title": "T", "details": "x" * 2001}},
    }
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        resp = client.put(f"/api/boards/{board_id}", json=board, headers=headers)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------

def test_get_nonexistent_board_returns_404(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        resp = client.get("/api/boards/does-not-exist", headers=headers)
    assert resp.status_code == 404


def test_delete_nonexistent_board_returns_404(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        resp = client.delete("/api/boards/does-not-exist", headers=headers)
    assert resp.status_code == 404


def test_expired_or_invalid_token_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        resp = client.get("/api/boards", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert resp.status_code == 401


def test_users_cannot_see_each_others_boards(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers_a = register_and_login(client, "alice")
        headers_b = register_and_login(client, "bob")
        board_a = client.post("/api/boards", json={"title": "Alice Private"}, headers=headers_a).json()["id"]
        boards_b = client.get("/api/boards", headers=headers_b).json()["boards"]
        assert not any(b["id"] == board_a for b in boards_b)
