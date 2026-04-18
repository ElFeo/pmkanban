import pytest
from fastapi.testclient import TestClient

from app.main import app


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def get_auth_header(client: TestClient, username: str = "user", password: str = "password") -> dict[str, str]:
    """Log in and return an Authorization header for subsequent requests."""
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, f"Login failed: {response.json()}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Authentication endpoint tests
# ---------------------------------------------------------------------------

def test_login_success(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))

    with TestClient(app) as client:
        response = client.post("/api/auth/login", json={"username": "user", "password": "password"})

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["username"] == "user"
    assert data["token_type"] == "bearer"


def test_login_wrong_password(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))

    with TestClient(app) as client:
        response = client.post("/api/auth/login", json={"username": "user", "password": "wrong"})

    assert response.status_code == 401


def test_login_wrong_username(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))

    with TestClient(app) as client:
        response = client.post("/api/auth/login", json={"username": "hacker", "password": "password"})

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Board endpoint authentication guard tests
# ---------------------------------------------------------------------------

def test_get_board_requires_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))

    with TestClient(app) as client:
        response = client.get("/api/board/user")

    assert response.status_code == 401  # HTTPBearer returns 401 when no credentials provided


def test_put_board_requires_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    payload = {
        "columns": [{"id": "col-a", "title": "Todo", "cardIds": ["card-1"]}],
        "cards": {"card-1": {"id": "card-1", "title": "Hello", "details": "World"}},
    }

    with TestClient(app) as client:
        response = client.put("/api/board/user", json=payload)

    assert response.status_code == 401


def test_get_board_invalid_token(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))

    with TestClient(app) as client:
        response = client.get("/api/board/user", headers={"Authorization": "Bearer bad-token"})

    assert response.status_code == 401


def test_get_board_cross_user_forbidden(tmp_path, monkeypatch):
    """Authenticated user cannot read another user's board."""
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))

    with TestClient(app) as client:
        headers = get_auth_header(client)
        response = client.get("/api/board/otheruser", headers=headers)

    assert response.status_code == 403


def test_put_board_cross_user_forbidden(tmp_path, monkeypatch):
    """Authenticated user cannot write to another user's board."""
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    payload = {
        "columns": [{"id": "col-a", "title": "Todo", "cardIds": ["card-1"]}],
        "cards": {"card-1": {"id": "card-1", "title": "Hello", "details": "World"}},
    }

    with TestClient(app) as client:
        headers = get_auth_header(client)
        response = client.put("/api/board/otheruser", json=payload, headers=headers)

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Board CRUD (happy path, authenticated)
# ---------------------------------------------------------------------------

def test_get_board_seeds_default(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))

    with TestClient(app) as client:
        headers = get_auth_header(client)
        response = client.get("/api/board/user", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data["columns"]) == 5
    assert "card-1" in data["cards"]


def test_put_board_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    payload = {
        "columns": [{"id": "col-a", "title": "Todo", "cardIds": ["card-1"]}],
        "cards": {"card-1": {"id": "card-1", "title": "Hello", "details": "World"}},
    }

    with TestClient(app) as client:
        headers = get_auth_header(client)
        put_response = client.put("/api/board/user", json=payload, headers=headers)
        get_response = client.get("/api/board/user", headers=headers)

    assert put_response.status_code == 200
    assert get_response.status_code == 200
    data = get_response.json()
    # columns core fields preserved (response may include new optional fields like wip_limit)
    assert len(data["columns"]) == 1
    assert data["columns"][0]["id"] == "col-a"
    assert data["columns"][0]["title"] == "Todo"
    assert data["columns"][0]["cardIds"] == ["card-1"]
    card = data["cards"]["card-1"]
    assert card["title"] == "Hello"
    assert card["details"] == "World"


# ---------------------------------------------------------------------------
# Validation: malformed / invalid board payloads
# ---------------------------------------------------------------------------

def test_put_board_missing_cards_field(tmp_path, monkeypatch):
    """Board payload missing the 'cards' field should return 422."""
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))

    with TestClient(app) as client:
        headers = get_auth_header(client)
        response = client.put("/api/board/user", json={"columns": []}, headers=headers)

    assert response.status_code == 422


def test_put_board_column_title_too_long(tmp_path, monkeypatch):
    """Column title exceeding max_length should return 422."""
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    long_title = "x" * 101  # Column.title max_length=100
    payload = {
        "columns": [{"id": "col-a", "title": long_title, "cardIds": []}],
        "cards": {},
    }

    with TestClient(app) as client:
        headers = get_auth_header(client)
        response = client.put("/api/board/user", json=payload, headers=headers)

    assert response.status_code == 422


def test_put_board_card_title_too_long(tmp_path, monkeypatch):
    """Card title exceeding max_length should return 422."""
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "test.db"))
    long_title = "x" * 201  # Card.title max_length=200
    payload = {
        "columns": [{"id": "col-a", "title": "Todo", "cardIds": ["card-1"]}],
        "cards": {"card-1": {"id": "card-1", "title": long_title, "details": "ok"}},
    }

    with TestClient(app) as client:
        headers = get_auth_header(client)
        response = client.put("/api/board/user", json=payload, headers=headers)

    assert response.status_code == 422
