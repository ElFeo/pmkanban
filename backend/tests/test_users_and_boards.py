"""
Tests for user registration, multi-board management, and board ownership enforcement.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def auth_header(client: TestClient, username: str, password: str) -> dict[str, str]:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.json()}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def register_and_login(client: TestClient, username: str, password: str = "Str0ngPass!") -> dict[str, str]:
    resp = client.post("/api/auth/register", json={"username": username, "password": password})
    assert resp.status_code == 201, f"Register failed: {resp.json()}"
    return auth_header(client, username, password)


VALID_BOARD = {
    "columns": [{"id": "col-a", "title": "Todo", "cardIds": ["card-1"]}],
    "cards": {"card-1": {"id": "card-1", "title": "Task", "details": "details"}},
}


# ---------------------------------------------------------------------------
# User registration
# ---------------------------------------------------------------------------

def test_register_success(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        resp = client.post("/api/auth/register", json={"username": "alice", "password": "Str0ngPass!"})
    assert resp.status_code == 201
    assert resp.json()["username"] == "alice"


def test_register_duplicate_username(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        client.post("/api/auth/register", json={"username": "alice", "password": "Str0ngPass!"})
        resp = client.post("/api/auth/register", json={"username": "alice", "password": "Other1Pass!"})
    assert resp.status_code == 409


def test_register_username_too_short(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        resp = client.post("/api/auth/register", json={"username": "ab", "password": "Str0ngPass!"})
    assert resp.status_code == 422


def test_register_password_too_short(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        resp = client.post("/api/auth/register", json={"username": "alice", "password": "short"})
    assert resp.status_code == 422


def test_register_invalid_username_chars(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        resp = client.post("/api/auth/register", json={"username": "alice bob", "password": "Str0ngPass!"})
    assert resp.status_code == 422


def test_registered_user_can_login(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        client.post("/api/auth/register", json={"username": "alice", "password": "Str0ngPass!"})
        resp = client.post("/api/auth/login", json={"username": "alice", "password": "Str0ngPass!"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "alice"


def test_registered_user_wrong_password(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        client.post("/api/auth/register", json={"username": "alice", "password": "Str0ngPass!"})
        resp = client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Board listing (GET /api/boards)
# ---------------------------------------------------------------------------

def test_list_boards_empty_initially(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        resp = client.get("/api/boards", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["boards"] == []


def test_list_boards_requires_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        resp = client.get("/api/boards")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Board creation (POST /api/boards)
# ---------------------------------------------------------------------------

def test_create_board(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        resp = client.post("/api/boards", json={"title": "Sprint 1"}, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Sprint 1"
    assert "id" in data


def test_create_multiple_boards(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        client.post("/api/boards", json={"title": "Board A"}, headers=headers)
        client.post("/api/boards", json={"title": "Board B"}, headers=headers)
        resp = client.get("/api/boards", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["boards"]) == 2
    titles = {b["title"] for b in resp.json()["boards"]}
    assert titles == {"Board A", "Board B"}


def test_create_board_title_too_long(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        resp = client.post("/api/boards", json={"title": "x" * 101}, headers=headers)
    assert resp.status_code == 422


def test_boards_isolated_between_users(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        alice = register_and_login(client, "alice")
        bob = register_and_login(client, "bob")
        client.post("/api/boards", json={"title": "Alice Board"}, headers=alice)
        resp = client.get("/api/boards", headers=bob)
    assert resp.json()["boards"] == []


# ---------------------------------------------------------------------------
# Get board data (GET /api/boards/{board_id})
# ---------------------------------------------------------------------------

def test_get_board_seeds_empty_board(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_resp = client.post("/api/boards", json={"title": "My Board"}, headers=headers)
        board_id = board_resp.json()["id"]
        resp = client.get(f"/api/boards/{board_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    # seeded with default columns
    assert len(data["columns"]) == 5
    assert "card-1" in data["cards"]


def test_get_board_forbidden_for_other_user(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        alice = register_and_login(client, "alice")
        bob = register_and_login(client, "bob")
        board_resp = client.post("/api/boards", json={"title": "Alice Board"}, headers=alice)
        board_id = board_resp.json()["id"]
        resp = client.get(f"/api/boards/{board_id}", headers=bob)
    assert resp.status_code == 403


def test_get_board_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        resp = client.get("/api/boards/nonexistent-board-id", headers=headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Update board data (PUT /api/boards/{board_id})
# ---------------------------------------------------------------------------

def test_update_board_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "My Board"}, headers=headers).json()["id"]
        client.put(f"/api/boards/{board_id}", json=VALID_BOARD, headers=headers)
        resp = client.get(f"/api/boards/{board_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["columns"] == VALID_BOARD["columns"]
    assert data["cards"]["card-1"]["title"] == "Task"


def test_update_board_forbidden_for_other_user(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        alice = register_and_login(client, "alice")
        bob = register_and_login(client, "bob")
        board_id = client.post("/api/boards", json={"title": "Alice Board"}, headers=alice).json()["id"]
        resp = client.put(f"/api/boards/{board_id}", json=VALID_BOARD, headers=bob)
    assert resp.status_code == 403


def test_update_board_missing_card_reference(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    bad_board = {
        "columns": [{"id": "col-a", "title": "Todo", "cardIds": ["missing-card"]}],
        "cards": {},
    }
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "My Board"}, headers=headers).json()["id"]
        resp = client.put(f"/api/boards/{board_id}", json=bad_board, headers=headers)
    assert resp.status_code == 422  # invalid card reference → unprocessable


def test_two_boards_data_isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        id_a = client.post("/api/boards", json={"title": "Board A"}, headers=headers).json()["id"]
        id_b = client.post("/api/boards", json={"title": "Board B"}, headers=headers).json()["id"]
        client.put(f"/api/boards/{id_a}", json={
            "columns": [{"id": "col-a", "title": "Alpha", "cardIds": ["card-a"]}],
            "cards": {"card-a": {"id": "card-a", "title": "A Task", "details": ""}},
        }, headers=headers)
        client.put(f"/api/boards/{id_b}", json={
            "columns": [{"id": "col-b", "title": "Beta", "cardIds": ["card-b"]}],
            "cards": {"card-b": {"id": "card-b", "title": "B Task", "details": ""}},
        }, headers=headers)
        resp_a = client.get(f"/api/boards/{id_a}", headers=headers).json()
        resp_b = client.get(f"/api/boards/{id_b}", headers=headers).json()
    assert resp_a["cards"]["card-a"]["title"] == "A Task"
    assert resp_b["cards"]["card-b"]["title"] == "B Task"
    assert "card-b" not in resp_a["cards"]
    assert "card-a" not in resp_b["cards"]


# ---------------------------------------------------------------------------
# Rename board (PATCH /api/boards/{board_id})
# ---------------------------------------------------------------------------

def test_rename_board(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "Old Name"}, headers=headers).json()["id"]
        resp = client.patch(f"/api/boards/{board_id}", json={"title": "New Name"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "New Name"


def test_rename_board_forbidden_for_other_user(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        alice = register_and_login(client, "alice")
        bob = register_and_login(client, "bob")
        board_id = client.post("/api/boards", json={"title": "Alice Board"}, headers=alice).json()["id"]
        resp = client.patch(f"/api/boards/{board_id}", json={"title": "Stolen"}, headers=bob)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Delete board (DELETE /api/boards/{board_id})
# ---------------------------------------------------------------------------

def test_delete_board(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "Temp Board"}, headers=headers).json()["id"]
        del_resp = client.delete(f"/api/boards/{board_id}", headers=headers)
        list_resp = client.get("/api/boards", headers=headers)
    assert del_resp.status_code == 204
    assert list_resp.json()["boards"] == []


def test_delete_board_forbidden_for_other_user(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        alice = register_and_login(client, "alice")
        bob = register_and_login(client, "bob")
        board_id = client.post("/api/boards", json={"title": "Alice Board"}, headers=alice).json()["id"]
        resp = client.delete(f"/api/boards/{board_id}", headers=bob)
    assert resp.status_code == 403


def test_delete_board_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        resp = client.delete("/api/boards/nonexistent-id", headers=headers)
    assert resp.status_code == 404


def test_delete_board_removes_cards(tmp_path, monkeypatch):
    """Deleting a board should cascade-delete its columns and cards."""
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "Temp Board"}, headers=headers).json()["id"]
        client.put(f"/api/boards/{board_id}", json=VALID_BOARD, headers=headers)
        client.delete(f"/api/boards/{board_id}", headers=headers)
        resp = client.get(f"/api/boards/{board_id}", headers=headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# AI chat with board_id
# ---------------------------------------------------------------------------

def test_ai_chat_with_unknown_board_id(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        resp = client.post(
            "/api/ai/chat",
            json={"message": "hello", "board_id": "nonexistent"},
            headers=headers,
        )
    assert resp.status_code == 404


def test_ai_chat_with_other_users_board_id(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        alice = register_and_login(client, "alice")
        bob = register_and_login(client, "bob")
        board_id = client.post("/api/boards", json={"title": "Alice Board"}, headers=alice).json()["id"]
        resp = client.post(
            "/api/ai/chat",
            json={"message": "hello", "board_id": board_id},
            headers=bob,
        )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Legacy board endpoints still work
# ---------------------------------------------------------------------------

def test_legacy_get_board_still_works(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        resp = client.post("/api/auth/login", json={"username": "user", "password": "password"})
        headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
        resp = client.get("/api/board/user", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["columns"]) == 5


def test_legacy_put_board_still_works(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        resp = client.post("/api/auth/login", json={"username": "user", "password": "password"})
        headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
        put_resp = client.put("/api/board/user", json=VALID_BOARD, headers=headers)
        get_resp = client.get("/api/board/user", headers=headers)
    assert put_resp.status_code == 200
    data = get_resp.json()
    assert data["columns"] == VALID_BOARD["columns"]
    assert data["cards"]["card-1"]["title"] == "Task"
