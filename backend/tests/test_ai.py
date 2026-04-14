import os

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.mark.skipif(
    not os.getenv("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY is not set",
)
def test_ai_test_route_returns_response():
    with TestClient(app) as client:
        response = client.post("/api/ai/test", json={"prompt": "2+2"})

    assert response.status_code == 200
    data = response.json()
    assert "choices" in data
    assert isinstance(data["choices"], list)
    assert data["choices"]
    content = data["choices"][0].get("message", {}).get("content", "")
    assert "4" in content
