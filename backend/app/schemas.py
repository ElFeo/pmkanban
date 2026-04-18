from typing import Literal

from pydantic import BaseModel, Field


class Card(BaseModel):
    id: str = Field(max_length=100)
    title: str = Field(min_length=1, max_length=200)
    details: str = Field(max_length=2000)


class Column(BaseModel):
    id: str = Field(max_length=100)
    title: str = Field(min_length=1, max_length=100)
    cardIds: list[str]


class BoardData(BaseModel):
    columns: list[Column]
    cards: dict[str, Card]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AIChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=40)
    board_id: str | None = None


class AIChatResult(BaseModel):
    reply: str | None = None
    board: BoardData | None = None


class AIChatResponse(BaseModel):
    reply: str
    board: BoardData | None = None
    applied: bool


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class LoginResponse(BaseModel):
    access_token: str
    username: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(min_length=8, max_length=200)


class RegisterResponse(BaseModel):
    username: str
    message: str = "Account created successfully"


class BoardSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class BoardListResponse(BaseModel):
    boards: list[BoardSummary]


class BoardCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=100)


class BoardRenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=100)
