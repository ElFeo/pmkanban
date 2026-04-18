"""Tests for card assignee field, GET /api/users, and GET /api/me/tasks."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


def register_and_login(client, username, password="Str0ngPass!"):
    client.post("/api/auth/register", json={"username": username, "password": password})
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def make_board_with_assigned_card(assignee=None):
    card = {"id": "card-1", "title": "Task", "details": "", "assignee": assignee}
    return {
        "columns": [{"id": "col-a", "title": "Todo", "cardIds": ["card-1"]}],
        "cards": {"card-1": card},
    }


# ---------------------------------------------------------------------------
# Assignee field round-trips
# ---------------------------------------------------------------------------

def test_assignee_stored_and_returned(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        client.put(f"/api/boards/{board_id}", json=make_board_with_assigned_card("alice"), headers=headers)
        data = client.get(f"/api/boards/{board_id}", headers=headers).json()
    assert data["cards"]["card-1"]["assignee"] == "alice"


def test_assignee_null_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    board = {
        "columns": [{"id": "col-a", "title": "Todo", "cardIds": ["c1"]}],
        "cards": {"c1": {"id": "c1", "title": "T", "details": ""}},
    }
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        client.put(f"/api/boards/{board_id}", json=board, headers=headers)
        data = client.get(f"/api/boards/{board_id}", headers=headers).json()
    assert data["cards"]["c1"]["assignee"] is None


def test_assignee_can_be_cleared(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        client.put(f"/api/boards/{board_id}", json=make_board_with_assigned_card("alice"), headers=headers)
        # Now clear assignee
        client.put(f"/api/boards/{board_id}", json=make_board_with_assigned_card(None), headers=headers)
        data = client.get(f"/api/boards/{board_id}", headers=headers).json()
    assert data["cards"]["card-1"]["assignee"] is None


# ---------------------------------------------------------------------------
# GET /api/users
# ---------------------------------------------------------------------------

def test_list_users_requires_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        resp = client.get("/api/users")
    assert resp.status_code == 401


def test_list_users_returns_registered_users(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers_a = register_and_login(client, "alice")
        register_and_login(client, "bob")
        resp = client.get("/api/users", headers=headers_a)
    assert resp.status_code == 200
    usernames = resp.json()["usernames"]
    assert "alice" in usernames
    assert "bob" in usernames


def test_list_users_is_sorted(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "zelda")
        register_and_login(client, "anna")
        register_and_login(client, "mike")
        resp = client.get("/api/users", headers=headers)
    usernames = resp.json()["usernames"]
    assert usernames == sorted(usernames)


# ---------------------------------------------------------------------------
# GET /api/me/tasks
# ---------------------------------------------------------------------------

def test_my_tasks_requires_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        resp = client.get("/api/me/tasks")
    assert resp.status_code == 401


def test_my_tasks_empty_initially(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        resp = client.get("/api/me/tasks", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["assignee"] == "alice"
    assert data["tasks"] == []


def test_my_tasks_returns_assigned_cards(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "My Board"}, headers=headers).json()["id"]
        client.put(f"/api/boards/{board_id}", json=make_board_with_assigned_card("alice"), headers=headers)
        resp = client.get("/api/me/tasks", headers=headers)
    assert resp.status_code == 200
    tasks = resp.json()["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Task"
    assert tasks[0]["assignee"] == "alice"
    assert tasks[0]["board_title"] == "My Board"


def test_my_tasks_excludes_other_assignees(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    board = {
        "columns": [{"id": "col-a", "title": "Todo", "cardIds": ["c1", "c2"]}],
        "cards": {
            "c1": {"id": "c1", "title": "Alice task", "details": "", "assignee": "alice"},
            "c2": {"id": "c2", "title": "Bob task", "details": "", "assignee": "bob"},
        },
    }
    with TestClient(app) as client:
        headers_alice = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers_alice).json()["id"]
        client.put(f"/api/boards/{board_id}", json=board, headers=headers_alice)
        resp = client.get("/api/me/tasks", headers=headers_alice)
    tasks = resp.json()["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Alice task"


def test_my_tasks_across_multiple_boards(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        for i in range(3):
            board_id = client.post("/api/boards", json={"title": f"Board {i}"}, headers=headers).json()["id"]
            board = {
                "columns": [{"id": f"col-{i}", "title": "Todo", "cardIds": [f"card-{i}"]}],
                "cards": {f"card-{i}": {"id": f"card-{i}", "title": "Task", "details": "", "assignee": "alice"}},
            }
            client.put(f"/api/boards/{board_id}", json=board, headers=headers)
        resp = client.get("/api/me/tasks", headers=headers)
    tasks = resp.json()["tasks"]
    assert len(tasks) == 3
    board_titles = {t["board_title"] for t in tasks}
    assert board_titles == {"Board 0", "Board 1", "Board 2"}


def test_my_tasks_does_not_show_other_users_boards(tmp_path, monkeypatch):
    """Alice cannot see tasks from Bob's boards even if assigned to alice."""
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers_alice = register_and_login(client, "alice")
        headers_bob = register_and_login(client, "bob")
        # Bob creates a board and assigns card to alice
        board_id = client.post("/api/boards", json={"title": "Bob board"}, headers=headers_bob).json()["id"]
        client.put(f"/api/boards/{board_id}", json=make_board_with_assigned_card("alice"), headers=headers_bob)
        # Alice's tasks should be empty (she only sees her own boards)
        resp = client.get("/api/me/tasks", headers=headers_alice)
    assert resp.json()["tasks"] == []
