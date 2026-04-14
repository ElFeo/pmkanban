import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .schemas import BoardData, Card, Column

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = BASE_DIR / "data.db"


def get_db_path() -> Path:
    env_path = os.getenv("PM_DB_PATH")
    return Path(env_path) if env_path else DEFAULT_DB_PATH


@contextmanager
def get_connection():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS boards (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS columns (
                id TEXT PRIMARY KEY,
                board_id TEXT NOT NULL,
                title TEXT NOT NULL,
                position INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(board_id) REFERENCES boards(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cards (
                id TEXT PRIMARY KEY,
                board_id TEXT NOT NULL,
                column_id TEXT NOT NULL,
                title TEXT NOT NULL,
                details TEXT NOT NULL,
                position INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(board_id) REFERENCES boards(id),
                FOREIGN KEY(column_id) REFERENCES columns(id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_boards_user ON boards(user_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_columns_board ON columns(board_id, position)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cards_board ON cards(board_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cards_column ON cards(column_id, position)"
        )


def _seed_board() -> BoardData:
    columns = [
        Column(id="col-backlog", title="Backlog", cardIds=["card-1", "card-2"]),
        Column(id="col-discovery", title="Discovery", cardIds=["card-3"]),
        Column(id="col-progress", title="In Progress", cardIds=["card-4", "card-5"]),
        Column(id="col-review", title="Review", cardIds=["card-6"]),
        Column(id="col-done", title="Done", cardIds=["card-7", "card-8"]),
    ]
    cards = {
        "card-1": Card(
            id="card-1",
            title="Align roadmap themes",
            details="Draft quarterly themes with impact statements and metrics.",
        ),
        "card-2": Card(
            id="card-2",
            title="Gather customer signals",
            details="Review support tags, sales notes, and churn feedback.",
        ),
        "card-3": Card(
            id="card-3",
            title="Prototype analytics view",
            details="Sketch initial dashboard layout and key drill-downs.",
        ),
        "card-4": Card(
            id="card-4",
            title="Refine status language",
            details="Standardize column labels and tone across the board.",
        ),
        "card-5": Card(
            id="card-5",
            title="Design card layout",
            details="Add hierarchy and spacing for scanning dense lists.",
        ),
        "card-6": Card(
            id="card-6",
            title="QA micro-interactions",
            details="Verify hover, focus, and loading states.",
        ),
        "card-7": Card(
            id="card-7",
            title="Ship marketing page",
            details="Final copy approved and asset pack delivered.",
        ),
        "card-8": Card(
            id="card-8",
            title="Close onboarding sprint",
            details="Document release notes and share internally.",
        ),
    }
    return BoardData(columns=columns, cards=cards)


def _ensure_user_and_board(conn: sqlite3.Connection, username: str) -> str:
    user_id = username
    board_id = f"board-{username}"
    now = _now()

    conn.execute(
        "INSERT OR IGNORE INTO users (id, username, created_at) VALUES (?, ?, ?)",
        (user_id, username, now),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO boards (id, user_id, title, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (board_id, user_id, "Main board", now, now),
    )
    return board_id


def _board_has_columns(conn: sqlite3.Connection, board_id: str) -> bool:
    row = conn.execute(
        "SELECT COUNT(1) AS count FROM columns WHERE board_id = ?",
        (board_id,),
    ).fetchone()
    return bool(row and row["count"] > 0)


def _insert_board(conn: sqlite3.Connection, board_id: str, board: BoardData) -> None:
    now = _now()
    for col_index, column in enumerate(board.columns):
        conn.execute(
            """
            INSERT INTO columns (id, board_id, title, position, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (column.id, board_id, column.title, col_index, now, now),
        )
        for card_index, card_id in enumerate(column.cardIds):
            card = board.cards[card_id]
            conn.execute(
                """
                INSERT INTO cards (
                    id, board_id, column_id, title, details, position, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    card.id,
                    board_id,
                    column.id,
                    card.title,
                    card.details,
                    card_index,
                    now,
                    now,
                ),
            )


def _clear_board(conn: sqlite3.Connection, board_id: str) -> None:
    conn.execute("DELETE FROM cards WHERE board_id = ?", (board_id,))
    conn.execute("DELETE FROM columns WHERE board_id = ?", (board_id,))


def get_board(username: str) -> BoardData:
    with get_connection() as conn:
        board_id = _ensure_user_and_board(conn, username)
        if not _board_has_columns(conn, board_id):
            _insert_board(conn, board_id, _seed_board())

        columns_rows = conn.execute(
            "SELECT id, title FROM columns WHERE board_id = ? ORDER BY position",
            (board_id,),
        ).fetchall()
        card_rows = conn.execute(
            """
            SELECT id, column_id, title, details
            FROM cards
            WHERE board_id = ?
            ORDER BY column_id, position
            """,
            (board_id,),
        ).fetchall()

        cards: dict[str, Card] = {}
        card_ids_by_column: dict[str, list[str]] = {row["id"]: [] for row in columns_rows}
        for row in card_rows:
            card = Card(id=row["id"], title=row["title"], details=row["details"])
            cards[card.id] = card
            card_ids_by_column[row["column_id"]].append(card.id)

        columns = [
            Column(id=row["id"], title=row["title"], cardIds=card_ids_by_column[row["id"]])
            for row in columns_rows
        ]

        return BoardData(columns=columns, cards=cards)


def save_board(username: str, board: BoardData) -> BoardData:
    with get_connection() as conn:
        board_id = _ensure_user_and_board(conn, username)
        _clear_board(conn, board_id)
        _insert_board(conn, board_id, board)
        conn.execute(
            "UPDATE boards SET updated_at = ? WHERE id = ?",
            (_now(), board_id),
        )

    return get_board(username)
