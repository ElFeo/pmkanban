import json
import logging
import os
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
from time import time
from typing import Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from .auth import create_access_token, get_current_user, hash_password, verify_credentials, verify_password
from .db import (
    add_comment,
    create_board,
    create_user,
    delete_board,
    delete_comment,
    get_board_activity,
    get_board_by_id,
    get_board_stats,
    get_comments,
    get_my_tasks,
    get_or_create_first_board_id,
    get_user_by_username,
    get_user_profile,
    init_db,
    list_boards,
    list_users,
    log_activity,
    rename_board,
    save_board_by_id,
    update_user_password,
)
from .schemas import (
    ActivityLog,
    AIChatRequest,
    AIChatResponse,
    AIChatResult,
    BoardCreateRequest,
    BoardData,
    BoardListResponse,
    BoardRenameRequest,
    BoardStats,
    BoardSummary,
    ChangePasswordRequest,
    Comment,
    CommentCreate,
    CommentList,
    LoginRequest,
    LoginResponse,
    MyTasksResponse,
    RegisterRequest,
    RegisterResponse,
    UserListResponse,
    UserProfile,
)

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if not os.getenv("OPENROUTER_API_KEY"):
        logger.warning("OPENROUTER_API_KEY is not set — AI features will be unavailable")
    yield


app = FastAPI(lifespan=lifespan)
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
    # Enforce WIP limits
    for col in board.columns:
        if col.wip_limit is not None and len(col.cardIds) > col.wip_limit:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Column '{col.title}' has {len(col.cardIds)} cards but WIP limit is {col.wip_limit}",
            )
    try:
        result = save_board_by_id(board_id, current_user, board)
        card_count = sum(len(col.cardIds) for col in board.columns)
        log_activity(board_id, "board_updated", f"{card_count} cards across {len(board.columns)} columns")
        return result
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
        log_activity(board_id, "board_renamed", f"Renamed to '{request.title}'")
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
# Board stats + activity routes
# ---------------------------------------------------------------------------

@app.get("/api/boards/{board_id}/stats", response_model=BoardStats)
def get_stats(
    board_id: str,
    current_user: str = Depends(get_current_user),
) -> BoardStats:
    try:
        stats = get_board_stats(board_id, current_user)
        return BoardStats(**stats)
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")


@app.get("/api/boards/{board_id}/activity", response_model=ActivityLog)
def get_activity(
    board_id: str,
    current_user: str = Depends(get_current_user),
) -> ActivityLog:
    try:
        entries = get_board_activity(board_id, current_user)
        return ActivityLog(board_id=board_id, entries=entries)
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")


# ---------------------------------------------------------------------------
# Card comments routes
# ---------------------------------------------------------------------------

@app.post("/api/boards/{board_id}/cards/{card_id}/comments", response_model=Comment, status_code=201)
def create_comment(
    board_id: str,
    card_id: str,
    body: CommentCreate,
    current_user: str = Depends(get_current_user),
) -> Comment:
    try:
        comment = add_comment(board_id, card_id, current_user, body.content)
        return Comment(**comment)
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@app.get("/api/boards/{board_id}/cards/{card_id}/comments", response_model=CommentList)
def list_comments(
    board_id: str,
    card_id: str,
    current_user: str = Depends(get_current_user),
) -> CommentList:
    try:
        comments = get_comments(board_id, card_id, current_user)
        return CommentList(card_id=card_id, comments=comments)
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@app.delete("/api/boards/{board_id}/cards/{card_id}/comments/{comment_id}", status_code=204)
def remove_comment(
    board_id: str,
    card_id: str,
    comment_id: str,
    current_user: str = Depends(get_current_user),
) -> None:
    try:
        delete_comment(board_id, card_id, comment_id, current_user)
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


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
# User profile routes
# ---------------------------------------------------------------------------

@app.get("/api/me", response_model=UserProfile)
def get_profile(current_user: str = Depends(get_current_user)) -> UserProfile:
    profile = get_user_profile(current_user)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserProfile(**profile)


@app.patch("/api/me/password", status_code=204)
def change_password(
    request: ChangePasswordRequest,
    current_user: str = Depends(get_current_user),
) -> None:
    user = get_user_by_username(current_user)
    if user is None or not user.get("password_hash"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not verify_password(request.current_password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")
    update_user_password(current_user, hash_password(request.new_password))


@app.get("/api/me/tasks", response_model=MyTasksResponse)
def get_my_tasks_route(current_user: str = Depends(get_current_user)) -> MyTasksResponse:
    tasks = get_my_tasks(current_user)
    return MyTasksResponse(assignee=current_user, tasks=tasks)


@app.get("/api/users", response_model=UserListResponse)
def get_users(_: str = Depends(get_current_user)) -> UserListResponse:
    return UserListResponse(usernames=list_users())


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
# Static frontend (production only)
# ---------------------------------------------------------------------------

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
