import os
import sqlite3
import uuid
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


def _new_id() -> str:
    return str(uuid.uuid4())


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        # Migrate existing DBs that lack password_hash column
        try:
            conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
        except Exception:
            pass

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
        conn.execute("CREATE INDEX IF NOT EXISTS idx_boards_user ON boards(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_columns_board ON columns(board_id, position)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cards_board ON cards(board_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cards_column ON cards(column_id, position)")


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

def create_user(username: str, password_hash: str) -> str:
    """Create a new user; returns user_id. Raises ValueError if username taken."""
    user_id = _new_id()
    now = _now()
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            raise ValueError(f"Username '{username}' is already taken")
        conn.execute(
            "INSERT INTO users (id, username, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (user_id, username, password_hash, now),
        )
    return user_id


def get_user_by_username(username: str) -> dict | None:
    """Return user record dict or None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if row is None:
            return None
        return dict(row)


def upsert_demo_user(username: str, password_hash: str) -> str:
    """Insert demo user if not present, update hash if already there. Returns user_id."""
    now = _now()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE username = ?",
                (password_hash, username),
            )
            return row["id"]
        user_id = _new_id()
        conn.execute(
            "INSERT INTO users (id, username, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (user_id, username, password_hash, now),
        )
        return user_id


# ---------------------------------------------------------------------------
# Board management (multi-board)
# ---------------------------------------------------------------------------

def _ensure_user(conn: sqlite3.Connection, username: str) -> str:
    """Ensure user record exists; return user_id. Creates user without password hash if missing."""
    row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if row:
        return row["id"]
    user_id = _new_id()
    conn.execute(
        "INSERT INTO users (id, username, created_at) VALUES (?, ?, ?)",
        (user_id, username, _now()),
    )
    return user_id


def _get_or_create_default_board(conn: sqlite3.Connection, user_id: str, username: str) -> str:
    """Get or create the user's default board; return board_id."""
    row = conn.execute(
        "SELECT id FROM boards WHERE user_id = ? ORDER BY created_at ASC LIMIT 1",
        (user_id,),
    ).fetchone()
    if row:
        return row["id"]

    board_id = _new_id()
    now = _now()
    conn.execute(
        "INSERT INTO boards (id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (board_id, user_id, "Main Board", now, now),
    )
    return board_id


def list_boards(username: str) -> list[dict]:
    """Return list of board summaries for a user."""
    with get_connection() as conn:
        user_id = _ensure_user(conn, username)
        rows = conn.execute(
            "SELECT id, title, created_at, updated_at FROM boards WHERE user_id = ? ORDER BY created_at ASC",
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def create_board(username: str, title: str) -> dict:
    """Create a new board for the user; return board summary."""
    board_id = _new_id()
    now = _now()
    with get_connection() as conn:
        user_id = _ensure_user(conn, username)
        conn.execute(
            "INSERT INTO boards (id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (board_id, user_id, title, now, now),
        )
    return {"id": board_id, "title": title, "created_at": now, "updated_at": now}


def _assert_board_owner(conn: sqlite3.Connection, board_id: str, username: str) -> str:
    """Check board exists and belongs to username; return user_id. Raises ValueError otherwise."""
    row = conn.execute(
        """
        SELECT boards.id, users.username
        FROM boards
        JOIN users ON boards.user_id = users.id
        WHERE boards.id = ?
        """,
        (board_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Board not found")
    if row["username"] != username:
        raise PermissionError("Board does not belong to this user")
    return row["id"]


def rename_board(board_id: str, username: str, title: str) -> None:
    """Rename a board. Raises ValueError/PermissionError on failure."""
    with get_connection() as conn:
        _assert_board_owner(conn, board_id, username)
        conn.execute(
            "UPDATE boards SET title = ?, updated_at = ? WHERE id = ?",
            (title, _now(), board_id),
        )


def delete_board(board_id: str, username: str) -> None:
    """Delete a board and all its columns/cards. Raises if not found or wrong owner."""
    with get_connection() as conn:
        _assert_board_owner(conn, board_id, username)
        conn.execute("DELETE FROM cards WHERE board_id = ?", (board_id,))
        conn.execute("DELETE FROM columns WHERE board_id = ?", (board_id,))
        conn.execute("DELETE FROM boards WHERE id = ?", (board_id,))


# ---------------------------------------------------------------------------
# Board data (columns + cards)
# ---------------------------------------------------------------------------

def _seed_board() -> BoardData:
    columns = [
        Column(id="col-backlog", title="Backlog", cardIds=["card-1", "card-2"]),
        Column(id="col-discovery", title="Discovery", cardIds=["card-3"]),
        Column(id="col-progress", title="In Progress", cardIds=["card-4", "card-5"]),
        Column(id="col-review", title="Review", cardIds=["card-6"]),
        Column(id="col-done", title="Done", cardIds=["card-7", "card-8"]),
    ]
    cards = {
        "card-1": Card(id="card-1", title="Align roadmap themes", details="Draft quarterly themes with impact statements and metrics."),
        "card-2": Card(id="card-2", title="Gather customer signals", details="Review support tags, sales notes, and churn feedback."),
        "card-3": Card(id="card-3", title="Prototype analytics view", details="Sketch initial dashboard layout and key drill-downs."),
        "card-4": Card(id="card-4", title="Refine status language", details="Standardize column labels and tone across the board."),
        "card-5": Card(id="card-5", title="Design card layout", details="Add hierarchy and spacing for scanning dense lists."),
        "card-6": Card(id="card-6", title="QA micro-interactions", details="Verify hover, focus, and loading states."),
        "card-7": Card(id="card-7", title="Ship marketing page", details="Final copy approved and asset pack delivered."),
        "card-8": Card(id="card-8", title="Close onboarding sprint", details="Document release notes and share internally."),
    }
    return BoardData(columns=columns, cards=cards)


def _board_has_columns(conn: sqlite3.Connection, board_id: str) -> bool:
    row = conn.execute(
        "SELECT COUNT(1) AS count FROM columns WHERE board_id = ?", (board_id,)
    ).fetchone()
    return bool(row and row["count"] > 0)


def _insert_board_data(conn: sqlite3.Connection, board_id: str, board: BoardData) -> None:
    now = _now()
    for col_index, column in enumerate(board.columns):
        conn.execute(
            "INSERT INTO columns (id, board_id, title, position, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (column.id, board_id, column.title, col_index, now, now),
        )
        for card_index, card_id in enumerate(column.cardIds):
            card = board.cards.get(card_id)
            if card is None:
                raise ValueError(f"Column '{column.id}' references missing card '{card_id}'")
            conn.execute(
                """
                INSERT INTO cards (id, board_id, column_id, title, details, position, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (card.id, board_id, column.id, card.title, card.details, card_index, now, now),
            )


def _clear_board_data(conn: sqlite3.Connection, board_id: str) -> None:
    conn.execute("DELETE FROM cards WHERE board_id = ?", (board_id,))
    conn.execute("DELETE FROM columns WHERE board_id = ?", (board_id,))


def _read_board_data(conn: sqlite3.Connection, board_id: str) -> BoardData:
    columns_rows = conn.execute(
        "SELECT id, title FROM columns WHERE board_id = ? ORDER BY position",
        (board_id,),
    ).fetchall()
    card_rows = conn.execute(
        "SELECT id, column_id, title, details FROM cards WHERE board_id = ? ORDER BY column_id, position",
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


def get_board_by_id(board_id: str, username: str) -> BoardData:
    """Get board data by board_id, enforcing ownership. Seeds if empty."""
    with get_connection() as conn:
        _assert_board_owner(conn, board_id, username)
        if not _board_has_columns(conn, board_id):
            _insert_board_data(conn, board_id, _seed_board())
        return _read_board_data(conn, board_id)


def save_board_by_id(board_id: str, username: str, board: BoardData) -> BoardData:
    """Save board data by board_id, enforcing ownership."""
    with get_connection() as conn:
        _assert_board_owner(conn, board_id, username)
        _clear_board_data(conn, board_id)
        _insert_board_data(conn, board_id, board)
        conn.execute(
            "UPDATE boards SET updated_at = ? WHERE id = ?", (_now(), board_id)
        )
    return get_board_by_id(board_id, username)


def get_first_board_id(username: str) -> str | None:
    """Return the first board_id for a user, or None if no boards."""
    with get_connection() as conn:
        user_id = _ensure_user(conn, username)
        row = conn.execute(
            "SELECT id FROM boards WHERE user_id = ? ORDER BY created_at ASC LIMIT 1",
            (user_id,),
        ).fetchone()
        if row:
            return row["id"]
        return None


def get_or_create_first_board_id(username: str) -> str:
    """Return or create the first board for a user, seeding it if needed."""
    with get_connection() as conn:
        user_id = _ensure_user(conn, username)
        return _get_or_create_default_board(conn, user_id, username)


# ---------------------------------------------------------------------------
# Legacy helpers (kept for backward compatibility with old /api/board/{username})
# ---------------------------------------------------------------------------

def get_board(username: str) -> BoardData:
    board_id = get_or_create_first_board_id(username)
    return get_board_by_id(board_id, username)


def save_board(username: str, board: BoardData) -> BoardData:
    board_id = get_or_create_first_board_id(username)
    return save_board_by_id(board_id, username, board)
