import json
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
                wip_limit INTEGER,
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
                priority TEXT,
                due_date TEXT,
                labels TEXT NOT NULL DEFAULT '[]',
                archived INTEGER NOT NULL DEFAULT 0,
                assignee TEXT,
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

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS board_activity (
                id TEXT PRIMARY KEY,
                board_id TEXT NOT NULL,
                action TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(board_id) REFERENCES boards(id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_activity_board ON board_activity(board_id, created_at)")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS card_comments (
                id TEXT PRIMARY KEY,
                card_id TEXT NOT NULL,
                board_id TEXT NOT NULL,
                author TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(board_id) REFERENCES boards(id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_comments_card ON card_comments(card_id, created_at)")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS card_checklists (
                id TEXT PRIMARY KEY,
                card_id TEXT NOT NULL,
                board_id TEXT NOT NULL,
                text TEXT NOT NULL,
                checked INTEGER NOT NULL DEFAULT 0,
                position INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(board_id) REFERENCES boards(id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_checklists_card ON card_checklists(card_id, position)")

        # Migrate existing cards tables that lack new columns
        for col_def in [
            "ALTER TABLE cards ADD COLUMN priority TEXT",
            "ALTER TABLE cards ADD COLUMN due_date TEXT",
            "ALTER TABLE cards ADD COLUMN labels TEXT NOT NULL DEFAULT '[]'",
            "ALTER TABLE cards ADD COLUMN archived INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE cards ADD COLUMN assignee TEXT",
            "ALTER TABLE columns ADD COLUMN wip_limit INTEGER",
        ]:
            try:
                conn.execute(col_def)
            except Exception:
                pass


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


def get_user_profile(username: str) -> dict | None:
    """Return user profile with board count, or None if user not found."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, username, created_at FROM users WHERE username = ?", (username,)
        ).fetchone()
        if row is None:
            return None
        board_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM boards WHERE user_id = ?", (row["id"],)
        ).fetchone()["cnt"]
        return {
            "username": row["username"],
            "board_count": board_count,
            "created_at": row["created_at"],
        }


def update_user_password(username: str, new_hash: str) -> None:
    """Update the password hash for a user."""
    with get_connection() as conn:
        result = conn.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?", (new_hash, username)
        )
        if result.rowcount == 0:
            raise ValueError(f"User '{username}' not found")


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
        conn.execute("DELETE FROM card_comments WHERE board_id = ?", (board_id,))
        conn.execute("DELETE FROM card_checklists WHERE board_id = ?", (board_id,))
        conn.execute("DELETE FROM cards WHERE board_id = ?", (board_id,))
        conn.execute("DELETE FROM columns WHERE board_id = ?", (board_id,))
        conn.execute("DELETE FROM board_activity WHERE board_id = ?", (board_id,))
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
            "INSERT INTO columns (id, board_id, title, position, wip_limit, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (column.id, board_id, column.title, col_index, column.wip_limit, now, now),
        )
        for card_index, card_id in enumerate(column.cardIds):
            card = board.cards.get(card_id)
            if card is None:
                raise ValueError(f"Column '{column.id}' references missing card '{card_id}'")
            conn.execute(
                """
                INSERT INTO cards (id, board_id, column_id, title, details, priority, due_date, labels, archived, assignee, position, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    card.id, board_id, column.id, card.title, card.details,
                    card.priority, card.due_date, json.dumps(card.labels),
                    1 if card.archived else 0, card.assignee,
                    card_index, now, now,
                ),
            )


def _clear_board_data(conn: sqlite3.Connection, board_id: str) -> None:
    conn.execute("DELETE FROM card_checklists WHERE board_id = ?", (board_id,))
    conn.execute("DELETE FROM card_comments WHERE board_id = ?", (board_id,))
    conn.execute("DELETE FROM cards WHERE board_id = ?", (board_id,))
    conn.execute("DELETE FROM columns WHERE board_id = ?", (board_id,))


def _read_board_data(conn: sqlite3.Connection, board_id: str) -> BoardData:
    columns_rows = conn.execute(
        "SELECT id, title, wip_limit FROM columns WHERE board_id = ? ORDER BY position",
        (board_id,),
    ).fetchall()
    card_rows = conn.execute(
        "SELECT id, column_id, title, details, priority, due_date, labels, archived, assignee FROM cards WHERE board_id = ? ORDER BY column_id, position",
        (board_id,),
    ).fetchall()

    cards: dict[str, Card] = {}
    card_ids_by_column: dict[str, list[str]] = {row["id"]: [] for row in columns_rows}
    for row in card_rows:
        labels = json.loads(row["labels"]) if row["labels"] else []
        card = Card(
            id=row["id"],
            title=row["title"],
            details=row["details"],
            priority=row["priority"],
            due_date=row["due_date"],
            labels=labels,
            archived=bool(row["archived"]),
            assignee=row["assignee"],
        )
        cards[card.id] = card
        card_ids_by_column[row["column_id"]].append(card.id)

    columns = [
        Column(id=row["id"], title=row["title"], cardIds=card_ids_by_column[row["id"]], wip_limit=row["wip_limit"])
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


# ---------------------------------------------------------------------------
# Activity log
# ---------------------------------------------------------------------------

def log_activity(board_id: str, action: str, detail: str = "") -> None:
    """Append an activity entry to the board's log."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO board_activity (id, board_id, action, detail, created_at) VALUES (?, ?, ?, ?, ?)",
            (_new_id(), board_id, action, detail, _now()),
        )


def get_board_activity(board_id: str, username: str, limit: int = 30) -> list[dict]:
    """Return recent activity entries for a board, enforcing ownership."""
    with get_connection() as conn:
        _assert_board_owner(conn, board_id, username)
        rows = conn.execute(
            "SELECT id, action, detail, created_at FROM board_activity WHERE board_id = ? ORDER BY created_at DESC LIMIT ?",
            (board_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Board statistics
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Card comments
# ---------------------------------------------------------------------------

def add_comment(board_id: str, card_id: str, username: str, content: str) -> dict:
    """Add a comment to a card. Validates board ownership and card existence."""
    comment_id = _new_id()
    now = _now()
    with get_connection() as conn:
        _assert_board_owner(conn, board_id, username)
        card_row = conn.execute(
            "SELECT id FROM cards WHERE id = ? AND board_id = ?", (card_id, board_id)
        ).fetchone()
        if card_row is None:
            raise ValueError(f"Card '{card_id}' not found in board '{board_id}'")
        conn.execute(
            "INSERT INTO card_comments (id, card_id, board_id, author, content, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (comment_id, card_id, board_id, username, content, now),
        )
    return {"id": comment_id, "card_id": card_id, "author": username, "content": content, "created_at": now}


def get_comments(board_id: str, card_id: str, username: str) -> list[dict]:
    """Return all comments for a card. Validates board ownership."""
    with get_connection() as conn:
        _assert_board_owner(conn, board_id, username)
        rows = conn.execute(
            "SELECT id, card_id, author, content, created_at FROM card_comments WHERE card_id = ? AND board_id = ? ORDER BY created_at ASC",
            (card_id, board_id),
        ).fetchall()
        return [dict(row) for row in rows]


def delete_comment(board_id: str, card_id: str, comment_id: str, username: str) -> None:
    """Delete a comment. Only the author or board owner may delete."""
    with get_connection() as conn:
        _assert_board_owner(conn, board_id, username)
        row = conn.execute(
            "SELECT id, author FROM card_comments WHERE id = ? AND card_id = ? AND board_id = ?",
            (comment_id, card_id, board_id),
        ).fetchone()
        if row is None:
            raise ValueError("Comment not found")
        if row["author"] != username:
            raise PermissionError("Cannot delete another user's comment")
        conn.execute("DELETE FROM card_comments WHERE id = ?", (comment_id,))


def get_checklist(board_id: str, card_id: str, username: str) -> list[dict]:
    with get_connection() as conn:
        _assert_board_owner(conn, board_id, username)
        rows = conn.execute(
            "SELECT id, card_id, text, checked, position FROM card_checklists WHERE card_id = ? AND board_id = ? ORDER BY position",
            (card_id, board_id),
        ).fetchall()
        return [{"id": r["id"], "card_id": r["card_id"], "text": r["text"], "checked": bool(r["checked"]), "position": r["position"]} for r in rows]


def add_checklist_item(board_id: str, card_id: str, username: str, text: str) -> dict:
    with get_connection() as conn:
        _assert_board_owner(conn, board_id, username)
        card_row = conn.execute("SELECT id FROM cards WHERE id = ? AND board_id = ?", (card_id, board_id)).fetchone()
        if card_row is None:
            raise ValueError(f"Card '{card_id}' not found in board '{board_id}'")
        pos_row = conn.execute(
            "SELECT COALESCE(MAX(position) + 1, 0) AS pos FROM card_checklists WHERE card_id = ? AND board_id = ?",
            (card_id, board_id),
        ).fetchone()
        pos = pos_row["pos"] if pos_row else 0
        item_id = _new_id()
        now = _now()
        conn.execute(
            "INSERT INTO card_checklists (id, card_id, board_id, text, checked, position, created_at) VALUES (?, ?, ?, ?, 0, ?, ?)",
            (item_id, card_id, board_id, text, pos, now),
        )
    return {"id": item_id, "card_id": card_id, "text": text, "checked": False, "position": pos}


def update_checklist_item(board_id: str, card_id: str, item_id: str, username: str, text: str | None, checked: bool | None) -> dict:
    with get_connection() as conn:
        _assert_board_owner(conn, board_id, username)
        row = conn.execute(
            "SELECT id, text, checked, position FROM card_checklists WHERE id = ? AND card_id = ? AND board_id = ?",
            (item_id, card_id, board_id),
        ).fetchone()
        if row is None:
            raise ValueError("Checklist item not found")
        new_text = text if text is not None else row["text"]
        new_checked = checked if checked is not None else bool(row["checked"])
        conn.execute(
            "UPDATE card_checklists SET text = ?, checked = ? WHERE id = ?",
            (new_text, 1 if new_checked else 0, item_id),
        )
    return {"id": item_id, "card_id": card_id, "text": new_text, "checked": new_checked, "position": row["position"]}


def delete_checklist_item(board_id: str, card_id: str, item_id: str, username: str) -> None:
    with get_connection() as conn:
        _assert_board_owner(conn, board_id, username)
        result = conn.execute(
            "DELETE FROM card_checklists WHERE id = ? AND card_id = ? AND board_id = ?",
            (item_id, card_id, board_id),
        )
        if result.rowcount == 0:
            raise ValueError("Checklist item not found")


def list_users() -> list[str]:
    """Return list of all registered usernames (for assignee dropdowns)."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT username FROM users ORDER BY username ASC"
        ).fetchall()
        return [row["username"] for row in rows]


def get_my_tasks(username: str) -> list[dict]:
    """Return all cards assigned to username, across all boards the user owns."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                c.id AS card_id,
                c.board_id,
                b.title AS board_title,
                col.title AS column_title,
                c.title,
                c.details,
                c.priority,
                c.due_date,
                c.labels,
                c.archived,
                c.assignee
            FROM cards c
            JOIN boards b ON b.id = c.board_id
            JOIN users u ON u.id = b.user_id
            JOIN columns col ON col.id = c.column_id
            WHERE c.assignee = ? AND u.username = ?
            ORDER BY c.due_date ASC NULLS LAST, b.title ASC, c.title ASC
            """,
            (username, username),
        ).fetchall()
        result = []
        for row in rows:
            labels = json.loads(row["labels"]) if row["labels"] else []
            result.append({
                "card_id": row["card_id"],
                "board_id": row["board_id"],
                "board_title": row["board_title"],
                "column_title": row["column_title"],
                "title": row["title"],
                "details": row["details"],
                "priority": row["priority"],
                "due_date": row["due_date"],
                "labels": labels,
                "archived": bool(row["archived"]),
                "assignee": row["assignee"],
            })
        return result


def get_board_stats(board_id: str, username: str) -> dict:
    """Return aggregate stats for a board: card counts per column, priority breakdown, overdue count."""
    from datetime import date
    today = date.today().isoformat()

    with get_connection() as conn:
        _assert_board_owner(conn, board_id, username)

        col_rows = conn.execute(
            """
            SELECT col.id AS column_id, col.title AS column_title, COUNT(c.id) AS card_count
            FROM columns col
            LEFT JOIN cards c ON c.column_id = col.id AND c.board_id = col.board_id
            WHERE col.board_id = ?
            GROUP BY col.id, col.title
            ORDER BY col.position
            """,
            (board_id,),
        ).fetchall()

        priority_rows = conn.execute(
            "SELECT priority, COUNT(*) AS cnt FROM cards WHERE board_id = ? GROUP BY priority",
            (board_id,),
        ).fetchall()

        overdue_row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM cards WHERE board_id = ? AND due_date IS NOT NULL AND due_date < ?",
            (board_id, today),
        ).fetchone()

        columns = [{"column_id": r["column_id"], "column_title": r["column_title"], "card_count": r["card_count"]} for r in col_rows]
        total = sum(c["card_count"] for c in columns)

        priority_map: dict[str, int] = {"low": 0, "medium": 0, "high": 0, "urgent": 0, "none": 0}
        for row in priority_rows:
            key = row["priority"] if row["priority"] else "none"
            priority_map[key] = row["cnt"]

        return {
            "board_id": board_id,
            "total_cards": total,
            "overdue_count": overdue_row["cnt"] if overdue_row else 0,
            "columns": columns,
            "priority_breakdown": priority_map,
        }
