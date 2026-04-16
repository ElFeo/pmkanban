from typing import Literal

from pydantic import BaseModel, Field


class Card(BaseModel):
    id: str = Field(max_length=100)
    title: str = Field(max_length=200)
    details: str = Field(max_length=2000)


class Column(BaseModel):
    id: str = Field(max_length=100)
    title: str = Field(max_length=100)
    cardIds: list[str]


class BoardData(BaseModel):
    columns: list[Column]
    cards: dict[str, Card]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class AIChatRequest(BaseModel):
    message: str = Field(max_length=1000)
    history: list[ChatMessage] = Field(default_factory=list)


class AIChatResult(BaseModel):
    reply: str | None = None
    board: BoardData | None = None


class AIChatResponse(BaseModel):
    reply: str
    board: BoardData | None = None
    applied: bool


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    username: str
    token_type: str = "bearer"
