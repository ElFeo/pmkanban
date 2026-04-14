from fastapi.testclient import TestClient

from app.main import app


def test_get_board_seeds_default(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("PM_DB_PATH", str(db_path))

    with TestClient(app) as client:
        response = client.get("/api/board/user")

    assert response.status_code == 200
    data = response.json()
    assert len(data["columns"]) == 5
    assert "card-1" in data["cards"]


def test_put_board_persists(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("PM_DB_PATH", str(db_path))

    payload = {
        "columns": [
            {"id": "col-a", "title": "Todo", "cardIds": ["card-1"]}
        ],
        "cards": {
            "card-1": {"id": "card-1", "title": "Hello", "details": "World"}
        },
    }

    with TestClient(app) as client:
        put_response = client.put("/api/board/user", json=payload)
        get_response = client.get("/api/board/user")

    assert put_response.status_code == 200
    assert get_response.status_code == 200
    assert get_response.json() == payload
