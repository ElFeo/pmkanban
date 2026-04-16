import json
import logging
import os
from collections import defaultdict
from pathlib import Path
from threading import Lock
from time import time
from typing import Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from .auth import create_access_token, get_current_user, verify_credentials
from .db import get_board, init_db, save_board
from .schemas import (
    AIChatRequest,
    AIChatResponse,
    AIChatResult,
    BoardData,
    LoginRequest,
    LoginResponse,
)

logger = logging.getLogger(__name__)

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BASE_DIR.parent / "frontend" / "out"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openai/gpt-oss-120b"

# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ---------------------------------------------------------------------------
# In-memory rate limiter for the AI endpoint
# ---------------------------------------------------------------------------

_ai_request_log: dict[str, list[float]] = defaultdict(list)
_rate_lock = Lock()
RATE_LIMIT_WINDOW = 60   # seconds
RATE_LIMIT_MAX = 20      # requests per window per IP


def _check_ai_rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    now = time()
    with _rate_lock:
        window_start = now - RATE_LIMIT_WINDOW
        _ai_request_log[client_ip] = [
            t for t in _ai_request_log[client_ip] if t > window_start
        ]
        if len(_ai_request_log[client_ip]) >= RATE_LIMIT_MAX:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
            )
        _ai_request_log[client_ip].append(now)


# ---------------------------------------------------------------------------
# OpenRouter helpers
# ---------------------------------------------------------------------------

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

    # Detect raw BoardData at top level (has columns/cards but no reply/board wrapper)
    if (
        isinstance(parsed, dict)
        and "columns" in parsed
        and "cards" in parsed
        and "reply" not in parsed
    ):
        try:
            board = BoardData.model_validate(parsed)
        except ValidationError as exc:
            raise ValueError("AI response did not match schema") from exc
        return AIChatResult(reply="Updated board.", board=board)

    # Standard AIChatResult format: {reply, board?}
    try:
        result = AIChatResult.model_validate(parsed)
    except ValidationError as exc:
        raise ValueError("AI response did not match schema") from exc

    # Reject responses that provide a board without a reply (malformed structured response)
    if result.reply is None and result.board is not None:
        raise ValueError("AI response did not match schema")

    return result


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
    except (KeyError, ValueError) as exc:
        raise ValueError("Board references missing cards") from exc

    return updated, True


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.post("/api/auth/login", response_model=LoginResponse)
def login(request: LoginRequest) -> LoginResponse:
    if not verify_credentials(request.username, request.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_access_token(request.username)
    return LoginResponse(access_token=token, username=request.username)


# ---------------------------------------------------------------------------
# Board routes (require authentication)
# ---------------------------------------------------------------------------

@app.get("/api/board/{username}", response_model=BoardData)
def read_board(
    username: str,
    current_user: str = Depends(get_current_user),
) -> BoardData:
    if username != current_user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return get_board(username)


@app.put("/api/board/{username}", response_model=BoardData)
def update_board(
    username: str,
    board: BoardData,
    current_user: str = Depends(get_current_user),
) -> BoardData:
    if username != current_user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return save_board(username, board)


# ---------------------------------------------------------------------------
# AI chat route (requires authentication + rate limiting)
# ---------------------------------------------------------------------------

@app.post("/api/ai/chat", response_model=AIChatResponse)
def ai_chat(
    request: AIChatRequest,
    http_request: Request,
    current_user: str = Depends(get_current_user),
) -> AIChatResponse:
    _check_ai_rate_limit(http_request)
    board = get_board(current_user)
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
        updated_board, applied = _apply_ai_result(current_user, result)
        reply = result.reply or "Updated board."
        return AIChatResponse(reply=reply, board=updated_board, applied=applied)
    except ValueError as exc:
        # Log the full upstream response for debugging; return only the error class to the client
        logger.error("AI response processing failed: %s | upstream: %s", exc, response_data)
        raise HTTPException(
            status_code=502,
            detail={"error": str(exc)},
        ) from exc


# ---------------------------------------------------------------------------
# Utility routes
# ---------------------------------------------------------------------------

@app.get("/api/hello")
def hello() -> dict[str, str]:
    return {"message": "Hello from FastAPI", "status": "ok"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
def startup() -> None:
    init_db()
    if not os.getenv("OPENROUTER_API_KEY"):
        logger.warning(
            "OPENROUTER_API_KEY is not set — AI features will be unavailable at runtime"
        )


# ---------------------------------------------------------------------------
# Static frontend (production only)
# ---------------------------------------------------------------------------

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
