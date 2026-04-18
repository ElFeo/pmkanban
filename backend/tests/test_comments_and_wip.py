"""Tests for card comments and column WIP limits."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


def register_and_login(client, username, password="Str0ngPass!"):
    client.post("/api/auth/register", json={"username": username, "password": password})
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def make_board_with_card(card_id="card-1"):
    return {
        "columns": [{"id": "col-a", "title": "Todo", "cardIds": [card_id]}],
        "cards": {card_id: {"id": card_id, "title": "Task", "details": ""}},
    }


def setup_board_and_card(client, headers, card_id="card-1"):
    board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
    client.put(f"/api/boards/{board_id}", json=make_board_with_card(card_id), headers=headers)
    return board_id


# ---------------------------------------------------------------------------
# Card comments — happy path
# ---------------------------------------------------------------------------

def test_add_comment_returns_201(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = setup_board_and_card(client, headers)
        resp = client.post(
            f"/api/boards/{board_id}/cards/card-1/comments",
            json={"content": "First comment!"},
            headers=headers,
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["content"] == "First comment!"
    assert data["author"] == "alice"
    assert data["card_id"] == "card-1"


def test_list_comments_returns_all(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = setup_board_and_card(client, headers)
        url = f"/api/boards/{board_id}/cards/card-1/comments"
        client.post(url, json={"content": "Alpha"}, headers=headers)
        client.post(url, json={"content": "Beta"}, headers=headers)
        resp = client.get(url, headers=headers)
    assert resp.status_code == 200
    comments = resp.json()["comments"]
    assert len(comments) == 2
    assert comments[0]["content"] == "Alpha"
    assert comments[1]["content"] == "Beta"


def test_list_comments_empty_initially(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = setup_board_and_card(client, headers)
        resp = client.get(f"/api/boards/{board_id}/cards/card-1/comments", headers=headers)
    assert resp.json()["comments"] == []


def test_delete_own_comment(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = setup_board_and_card(client, headers)
        url = f"/api/boards/{board_id}/cards/card-1/comments"
        comment_id = client.post(url, json={"content": "Delete me"}, headers=headers).json()["id"]
        del_resp = client.delete(f"{url}/{comment_id}", headers=headers)
        list_resp = client.get(url, headers=headers)
    assert del_resp.status_code == 204
    assert list_resp.json()["comments"] == []


def test_comment_round_trip_id_preserved(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = setup_board_and_card(client, headers)
        url = f"/api/boards/{board_id}/cards/card-1/comments"
        created = client.post(url, json={"content": "Check ID"}, headers=headers).json()
        listed = client.get(url, headers=headers).json()["comments"]
    assert listed[0]["id"] == created["id"]


# ---------------------------------------------------------------------------
# Card comments — auth and access control
# ---------------------------------------------------------------------------

def test_add_comment_requires_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        resp = client.post("/api/boards/x/cards/y/comments", json={"content": "hi"})
    assert resp.status_code == 401


def test_list_comments_requires_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        resp = client.get("/api/boards/x/cards/y/comments")
    assert resp.status_code == 401


def test_comment_on_wrong_board_forbidden(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers_a = register_and_login(client, "alice")
        headers_b = register_and_login(client, "bob")
        board_id = setup_board_and_card(client, headers_a)
        resp = client.post(
            f"/api/boards/{board_id}/cards/card-1/comments",
            json={"content": "unauthorized"},
            headers=headers_b,
        )
    assert resp.status_code == 403


def test_comment_on_nonexistent_card_returns_404(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        resp = client.post(
            f"/api/boards/{board_id}/cards/no-such-card/comments",
            json={"content": "nope"},
            headers=headers,
        )
    assert resp.status_code == 404


def test_empty_comment_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = setup_board_and_card(client, headers)
        resp = client.post(
            f"/api/boards/{board_id}/cards/card-1/comments",
            json={"content": ""},
            headers=headers,
        )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Column WIP limits
# ---------------------------------------------------------------------------

def test_wip_limit_stored_and_returned(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    board = {
        "columns": [{"id": "col-a", "title": "Todo", "cardIds": [], "wip_limit": 3}],
        "cards": {},
    }
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        client.put(f"/api/boards/{board_id}", json=board, headers=headers)
        data = client.get(f"/api/boards/{board_id}", headers=headers).json()
    assert data["columns"][0]["wip_limit"] == 3


def test_wip_limit_null_default(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    board = {
        "columns": [{"id": "col-a", "title": "Todo", "cardIds": []}],
        "cards": {},
    }
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        client.put(f"/api/boards/{board_id}", json=board, headers=headers)
        data = client.get(f"/api/boards/{board_id}", headers=headers).json()
    assert data["columns"][0]["wip_limit"] is None


def test_wip_limit_exceeded_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    board = {
        "columns": [{"id": "col-a", "title": "Todo", "cardIds": ["c1", "c2", "c3"], "wip_limit": 2}],
        "cards": {
            "c1": {"id": "c1", "title": "T1", "details": ""},
            "c2": {"id": "c2", "title": "T2", "details": ""},
            "c3": {"id": "c3", "title": "T3", "details": ""},
        },
    }
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        resp = client.put(f"/api/boards/{board_id}", json=board, headers=headers)
    assert resp.status_code == 422
    assert "WIP limit" in resp.json()["detail"]


def test_wip_limit_at_boundary_accepted(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    board = {
        "columns": [{"id": "col-a", "title": "Todo", "cardIds": ["c1", "c2"], "wip_limit": 2}],
        "cards": {
            "c1": {"id": "c1", "title": "T1", "details": ""},
            "c2": {"id": "c2", "title": "T2", "details": ""},
        },
    }
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        resp = client.put(f"/api/boards/{board_id}", json=board, headers=headers)
    assert resp.status_code == 200


def test_wip_limit_zero_invalid(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    board = {
        "columns": [{"id": "col-a", "title": "Todo", "cardIds": [], "wip_limit": 0}],
        "cards": {},
    }
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        resp = client.put(f"/api/boards/{board_id}", json=board, headers=headers)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Card archiving
# ---------------------------------------------------------------------------

def test_archived_card_round_trips(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    board = {
        "columns": [{"id": "col-a", "title": "Done", "cardIds": ["c1"]}],
        "cards": {"c1": {"id": "c1", "title": "Old task", "details": "", "archived": True}},
    }
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        client.put(f"/api/boards/{board_id}", json=board, headers=headers)
        data = client.get(f"/api/boards/{board_id}", headers=headers).json()
    assert data["cards"]["c1"]["archived"] is True


def test_archived_defaults_false(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    board = {
        "columns": [{"id": "col-a", "title": "Todo", "cardIds": ["c1"]}],
        "cards": {"c1": {"id": "c1", "title": "Normal", "details": ""}},
    }
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        client.put(f"/api/boards/{board_id}", json=board, headers=headers)
        data = client.get(f"/api/boards/{board_id}", headers=headers).json()
    assert data["cards"]["c1"]["archived"] is False
