import json
import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from .db import get_board, init_db, save_board
from .schemas import AIChatRequest, AIChatResponse, AIChatResult, BoardData

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BASE_DIR.parent / "frontend" / "out"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openai/gpt-oss-120b"


class AITestRequest(BaseModel):
    prompt: str | None = None


def _call_openrouter(payload: dict[str, Any]) -> dict[str, Any]:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.post(OPENROUTER_URL, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


def _extract_message_content(response_data: dict[str, Any]) -> str:
    try:
        return response_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Unexpected AI response format") from exc


def _parse_ai_content(content: str) -> AIChatResult:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("AI response content is not valid JSON") from exc

    try:
        return AIChatResult.model_validate(parsed)
    except ValidationError as exc:
        try:
            board = BoardData.model_validate(parsed)
        except ValidationError:
            raise ValueError("AI response did not match schema") from exc

        return AIChatResult(reply="Updated board.", board=board)


def _build_ai_messages(board: BoardData, request: AIChatRequest) -> list[dict[str, str]]:
    system_prompt = (
        "You are a project management assistant. Return JSON only that matches "
        "the provided schema. If you change the board, return the full updated board."
    )
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": "Current board JSON:\n" + json.dumps(board.model_dump()),
        },
    ]

    for entry in request.history:
        messages.append({"role": entry.role, "content": entry.content})

    messages.append({"role": "user", "content": request.message})
    return messages


def _build_response_schema() -> dict[str, Any]:
    schema = AIChatResult.model_json_schema()
    return {"name": "kanban_response", "schema": schema, "strict": True}


def _apply_ai_result(username: str, result: AIChatResult) -> tuple[BoardData | None, bool]:
    if result.board is None:
        return None, False

    missing_cards: list[str] = []
    for column in result.board.columns:
        for card_id in column.cardIds:
            if card_id not in result.board.cards:
                missing_cards.append(card_id)

    if missing_cards:
        unique_missing = sorted(set(missing_cards))
        raise ValueError("Board references missing cards: " + ", ".join(unique_missing))

    try:
        updated = save_board(username, result.board)
    except KeyError as exc:
        raise ValueError("Board references missing cards") from exc

    return updated, True


@app.get("/api/hello")
def hello() -> dict[str, str]:
    return {"message": "Hello from FastAPI", "status": "ok"}


@app.post("/api/ai/test")
def ai_test(request: AITestRequest | None = None, prompt: str | None = None) -> dict[str, Any]:
    resolved_prompt = prompt or (request.prompt if request else None) or "2+2"
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": resolved_prompt}],
    }
    return _call_openrouter(payload)


@app.post("/api/ai/chat", response_model=AIChatResponse)
def ai_chat(request: AIChatRequest) -> AIChatResponse:
    board = get_board(request.username)
    messages = _build_ai_messages(board, request)
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "response_format": {"type": "json_schema", "json_schema": _build_response_schema()},
    }

    response_data = _call_openrouter(payload)
    try:
        content = _extract_message_content(response_data)
        result = _parse_ai_content(content)
        updated_board, applied = _apply_ai_result(request.username, result)
        reply = result.reply or "Updated board."
        return AIChatResponse(reply=reply, board=updated_board, applied=applied)
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "error": str(exc),
                "openrouter_response": response_data,
            },
        ) from exc


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
