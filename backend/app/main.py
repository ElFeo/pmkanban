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

from .auth import create_access_token, get_current_user, hash_password, verify_credentials
from .db import (
    create_board,
    create_user,
    delete_board,
    get_board_by_id,
    get_or_create_first_board_id,
    init_db,
    list_boards,
    rename_board,
    save_board_by_id,
)
from .schemas import (
    AIChatRequest,
    AIChatResponse,
    AIChatResult,
    BoardCreateRequest,
    BoardData,
    BoardListResponse,
    BoardRenameRequest,
    BoardSummary,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
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
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX = 20


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

    try:
        result = AIChatResult.model_validate(parsed)
    except ValidationError as exc:
        raise ValueError("AI response did not match schema") from exc

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


def _apply_ai_result(board_id: str, username: str, result: AIChatResult) -> tuple[BoardData | None, bool]:
    if result.board is None:
        return None, False

    missing_cards: list[str] = []
    for column in result.board.columns:
        for card_id in column.cardIds:
            if card_id not in result.board.cards:
                missing_cards.append(card_id)

    if missing_cards:
        raise ValueError("Board references missing cards: " + ", ".join(sorted(set(missing_cards))))

    try:
        updated = save_board_by_id(board_id, username, result.board)
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


@app.post("/api/auth/register", response_model=RegisterResponse, status_code=201)
def register(request: RegisterRequest) -> RegisterResponse:
    try:
        create_user(request.username, hash_password(request.password))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return RegisterResponse(username=request.username)


# ---------------------------------------------------------------------------
# Board management routes (multi-board)
# ---------------------------------------------------------------------------

@app.get("/api/boards", response_model=BoardListResponse)
def list_user_boards(current_user: str = Depends(get_current_user)) -> BoardListResponse:
    boards = list_boards(current_user)
    return BoardListResponse(
        boards=[BoardSummary(**b) for b in boards]
    )


@app.post("/api/boards", response_model=BoardSummary, status_code=201)
def create_user_board(
    request: BoardCreateRequest,
    current_user: str = Depends(get_current_user),
) -> BoardSummary:
    summary = create_board(current_user, request.title)
    return BoardSummary(**summary)


@app.get("/api/boards/{board_id}", response_model=BoardData)
def get_board_route(
    board_id: str,
    current_user: str = Depends(get_current_user),
) -> BoardData:
    try:
        return get_board_by_id(board_id, current_user)
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")


@app.put("/api/boards/{board_id}", response_model=BoardData)
def update_board_route(
    board_id: str,
    board: BoardData,
    current_user: str = Depends(get_current_user),
) -> BoardData:
    try:
        return save_board_by_id(board_id, current_user, board)
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower() and "card" not in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)


@app.patch("/api/boards/{board_id}", response_model=BoardSummary)
def rename_board_route(
    board_id: str,
    request: BoardRenameRequest,
    current_user: str = Depends(get_current_user),
) -> BoardSummary:
    try:
        rename_board(board_id, current_user, request.title)
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")
    boards = list_boards(current_user)
    board = next((b for b in boards if b["id"] == board_id), None)
    if board is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")
    return BoardSummary(**board)


@app.delete("/api/boards/{board_id}", status_code=204)
def delete_board_route(
    board_id: str,
    current_user: str = Depends(get_current_user),
) -> None:
    try:
        delete_board(board_id, current_user)
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")


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

    # Resolve board_id: use requested board or fall back to first/default board
    if request.board_id:
        board_id = request.board_id
        try:
            board = get_board_by_id(board_id, current_user)
        except PermissionError:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        except ValueError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")
    else:
        board_id = get_or_create_first_board_id(current_user)
        board = get_board_by_id(board_id, current_user)

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
        updated_board, applied = _apply_ai_result(board_id, current_user, result)
        reply = result.reply or "Updated board."
        return AIChatResponse(reply=reply, board=updated_board, applied=applied)
    except ValueError as exc:
        logger.error("AI response processing failed: %s | upstream: %s", exc, response_data)
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Legacy board routes (backward compatibility)
# ---------------------------------------------------------------------------

@app.get("/api/board/{username}", response_model=BoardData)
def read_board_legacy(
    username: str,
    current_user: str = Depends(get_current_user),
) -> BoardData:
    if username != current_user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    board_id = get_or_create_first_board_id(current_user)
    return get_board_by_id(board_id, current_user)


@app.put("/api/board/{username}", response_model=BoardData)
def update_board_legacy(
    username: str,
    board: BoardData,
    current_user: str = Depends(get_current_user),
) -> BoardData:
    if username != current_user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    board_id = get_or_create_first_board_id(current_user)
    return save_board_by_id(board_id, current_user, board)


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
        logger.warning("OPENROUTER_API_KEY is not set — AI features will be unavailable")


# ---------------------------------------------------------------------------
# Static frontend (production only)
# ---------------------------------------------------------------------------

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
