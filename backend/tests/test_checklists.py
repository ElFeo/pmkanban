"""Tests for card checklist (subtasks) feature."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


def register_and_login(client, username, password="Str0ngPass!"):
    client.post("/api/auth/register", json={"username": username, "password": password})
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def setup_board_and_card(client, headers, card_id="card-1"):
    board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
    client.put(
        f"/api/boards/{board_id}",
        json={
            "columns": [{"id": "col-a", "title": "Todo", "cardIds": [card_id]}],
            "cards": {card_id: {"id": card_id, "title": "Task", "details": ""}},
        },
        headers=headers,
    )
    return board_id


def checklist_url(board_id, card_id):
    return f"/api/boards/{board_id}/cards/{card_id}/checklist"


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_add_checklist_item_returns_201(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = setup_board_and_card(client, headers)
        resp = client.post(checklist_url(board_id, "card-1"), json={"text": "Do the thing"}, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["text"] == "Do the thing"
    assert data["checked"] is False
    assert "id" in data


def test_list_checklist_returns_all_items(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = setup_board_and_card(client, headers)
        url = checklist_url(board_id, "card-1")
        client.post(url, json={"text": "Alpha"}, headers=headers)
        client.post(url, json={"text": "Beta"}, headers=headers)
        resp = client.get(url, headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2
    assert items[0]["text"] == "Alpha"
    assert items[1]["text"] == "Beta"


def test_list_checklist_empty_initially(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = setup_board_and_card(client, headers)
        resp = client.get(checklist_url(board_id, "card-1"), headers=headers)
    assert resp.json()["items"] == []


def test_patch_checklist_item_check_it(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = setup_board_and_card(client, headers)
        url = checklist_url(board_id, "card-1")
        item_id = client.post(url, json={"text": "Step 1"}, headers=headers).json()["id"]
        patch_resp = client.patch(f"{url}/{item_id}", json={"checked": True}, headers=headers)
    assert patch_resp.status_code == 200
    assert patch_resp.json()["checked"] is True


def test_patch_checklist_item_rename(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = setup_board_and_card(client, headers)
        url = checklist_url(board_id, "card-1")
        item_id = client.post(url, json={"text": "Old text"}, headers=headers).json()["id"]
        patch_resp = client.patch(f"{url}/{item_id}", json={"text": "New text"}, headers=headers)
    assert patch_resp.json()["text"] == "New text"


def test_delete_checklist_item(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = setup_board_and_card(client, headers)
        url = checklist_url(board_id, "card-1")
        item_id = client.post(url, json={"text": "Delete me"}, headers=headers).json()["id"]
        del_resp = client.delete(f"{url}/{item_id}", headers=headers)
        list_resp = client.get(url, headers=headers)
    assert del_resp.status_code == 204
    assert list_resp.json()["items"] == []


def test_checklist_items_ordered_by_position(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = setup_board_and_card(client, headers)
        url = checklist_url(board_id, "card-1")
        for i in range(5):
            client.post(url, json={"text": f"Item {i}"}, headers=headers)
        resp = client.get(url, headers=headers)
    items = resp.json()["items"]
    positions = [i["position"] for i in items]
    assert positions == sorted(positions)
    assert [i["text"] for i in items] == [f"Item {i}" for i in range(5)]


def test_checklist_id_round_trips(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = setup_board_and_card(client, headers)
        url = checklist_url(board_id, "card-1")
        created = client.post(url, json={"text": "Check ID"}, headers=headers).json()
        listed = client.get(url, headers=headers).json()["items"]
    assert listed[0]["id"] == created["id"]


# ---------------------------------------------------------------------------
# Auth and access control
# ---------------------------------------------------------------------------

def test_checklist_requires_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        resp = client.get("/api/boards/x/cards/y/checklist")
    assert resp.status_code == 401


def test_checklist_wrong_board_forbidden(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers_a = register_and_login(client, "alice")
        headers_b = register_and_login(client, "bob")
        board_id = setup_board_and_card(client, headers_a)
        resp = client.post(
            checklist_url(board_id, "card-1"),
            json={"text": "sneaky"},
            headers=headers_b,
        )
    assert resp.status_code == 403


def test_checklist_nonexistent_card_returns_404(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = client.post("/api/boards", json={"title": "B"}, headers=headers).json()["id"]
        resp = client.post(
            checklist_url(board_id, "no-such-card"),
            json={"text": "nope"},
            headers=headers,
        )
    assert resp.status_code == 404


def test_empty_checklist_text_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = setup_board_and_card(client, headers)
        resp = client.post(checklist_url(board_id, "card-1"), json={"text": ""}, headers=headers)
    assert resp.status_code == 422


def test_delete_nonexistent_checklist_item_returns_404(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = setup_board_and_card(client, headers)
        resp = client.delete(checklist_url(board_id, "card-1") + "/no-such-id", headers=headers)
    assert resp.status_code == 404


def test_board_delete_cascades_to_checklists(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        headers = register_and_login(client, "alice")
        board_id = setup_board_and_card(client, headers)
        url = checklist_url(board_id, "card-1")
        client.post(url, json={"text": "Will be gone"}, headers=headers)
        client.delete(f"/api/boards/{board_id}", headers=headers)
        # Board is gone, so re-fetching should 403/404, not leave orphaned rows
        resp = client.get(url, headers=headers)
    assert resp.status_code in (403, 404)
