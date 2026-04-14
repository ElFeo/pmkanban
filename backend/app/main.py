from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .db import get_board, init_db, save_board
from .schemas import BoardData

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BASE_DIR.parent / "frontend" / "out"


@app.get("/api/hello")
def hello() -> dict[str, str]:
    return {"message": "Hello from FastAPI", "status": "ok"}


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
