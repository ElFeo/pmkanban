import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .db import get_board, init_db, save_board
from .schemas import BoardData

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BASE_DIR.parent / "frontend" / "out"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openai/gpt-oss-120b"


class AITestRequest(BaseModel):
    prompt: str | None = None


def _call_openrouter(prompt: str) -> dict[str, Any]:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.post(OPENROUTER_URL, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


@app.get("/api/hello")
def hello() -> dict[str, str]:
    return {"message": "Hello from FastAPI", "status": "ok"}


@app.post("/api/ai/test")
def ai_test(request: AITestRequest | None = None, prompt: str | None = None) -> dict[str, Any]:
    resolved_prompt = prompt or (request.prompt if request else None) or "2+2"
    return _call_openrouter(resolved_prompt)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/board/{username}", response_model=BoardData)
def read_board(username: str) -> BoardData:
    return get_board(username)


@app.put("/api/board/{username}", response_model=BoardData)
def update_board(username: str, board: BoardData) -> BoardData:
    return save_board(username, board)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
