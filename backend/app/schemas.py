from typing import Literal

from pydantic import BaseModel, Field


class Card(BaseModel):
    id: str
    title: str
    details: str


class Column(BaseModel):
    id: str
    title: str
    cardIds: list[str]


class BoardData(BaseModel):
    columns: list[Column]
    cards: dict[str, Card]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AIChatRequest(BaseModel):
    username: str
    message: str
    history: list[ChatMessage] = Field(default_factory=list)


class AIChatResult(BaseModel):
    reply: str | None = None
    board: BoardData | None = None


class AIChatResponse(BaseModel):
    reply: str
    board: BoardData | None = None
    applied: bool
