import json

import pytest

from app.db import init_db
from app.main import _apply_ai_result, _parse_ai_content
from app.schemas import AIChatResult, BoardData, Card, Column


def _sample_board() -> BoardData:
    return BoardData(
        columns=[Column(id="col-1", title="Todo", cardIds=["card-1"])],
        cards={"card-1": Card(id="card-1", title="Test", details="Details")},
    )


# ---------------------------------------------------------------------------
# _parse_ai_content — happy paths
# ---------------------------------------------------------------------------

def test_parse_ai_content_accepts_valid_json():
    board = _sample_board()
    content = json.dumps({"reply": "Updated", "board": board.model_dump()})

    result = _parse_ai_content(content)

    assert result.reply == "Updated"
    assert result.board is not None
    assert result.board.columns[0].id == "col-1"


def test_parse_ai_content_accepts_board_only():
    board = _sample_board()
    content = json.dumps(board.model_dump())

    result = _parse_ai_content(content)

    assert result.reply == "Updated board."
    assert result.board is not None
    assert result.board.columns[0].id == "col-1"


def test_parse_ai_content_accepts_reply_only():
    """A reply with no board update is valid."""
    content = json.dumps({"reply": "I can help with that."})

    result = _parse_ai_content(content)

    assert result.reply == "I can help with that."
    assert result.board is None


# ---------------------------------------------------------------------------
# _parse_ai_content — error paths
# ---------------------------------------------------------------------------

def test_parse_ai_content_rejects_missing_reply():
    content = json.dumps({"board": _sample_board().model_dump()})

    with pytest.raises(ValueError, match="schema"):
        _parse_ai_content(content)


def test_parse_ai_content_rejects_malformed_json():
    with pytest.raises(ValueError, match="not valid JSON"):
        _parse_ai_content("this is not json at all")


def test_parse_ai_content_rejects_truncated_json():
    with pytest.raises(ValueError, match="not valid JSON"):
        _parse_ai_content('{"reply": "Upd')


def test_parse_ai_content_rejects_wrong_type():
    """A JSON array is not a valid response."""
    with pytest.raises(ValueError, match="schema"):
        _parse_ai_content(json.dumps(["reply", "board"]))


def test_parse_ai_content_rejects_board_missing_required_field():
    """A board object inside the response that is missing 'cards' should fail validation."""
    content = json.dumps({"reply": "ok", "board": {"columns": []}})  # 'cards' required in BoardData

    with pytest.raises(ValueError, match="schema"):
        _parse_ai_content(content)


def test_parse_ai_content_rejects_card_title_too_long():
    """Card title that exceeds max_length should fail Pydantic validation."""
    long_title = "x" * 201
    board = {
        "columns": [{"id": "col-1", "title": "Todo", "cardIds": ["card-1"]}],
        "cards": {"card-1": {"id": "card-1", "title": long_title, "details": "ok"}},
    }
    content = json.dumps({"reply": "Updated", "board": board})

    with pytest.raises(ValueError, match="schema"):
        _parse_ai_content(content)


# ---------------------------------------------------------------------------
# _apply_ai_result — happy paths
# ---------------------------------------------------------------------------

def test_apply_ai_result_updates_board(tmp_path, monkeypatch):
    db_path = tmp_path / "ai.db"
    monkeypatch.setenv("PM_DB_PATH", str(db_path))
    from app.db import create_board, upsert_demo_user
    init_db()
    upsert_demo_user("user", "hashed")
    board_id = create_board("user", "Test Board")["id"]

    result = AIChatResult(reply="Updated", board=_sample_board())

    board, applied = _apply_ai_result(board_id, "user", result)

    assert applied is True
    assert board is not None
    assert board.cards["card-1"].title == "Test"


def test_apply_ai_result_no_update():
    result = AIChatResult(reply="No changes", board=None)

    board, applied = _apply_ai_result("dummy-board-id", "user", result)

    assert applied is False
    assert board is None


# ---------------------------------------------------------------------------
# _apply_ai_result — error paths
# ---------------------------------------------------------------------------

def test_apply_ai_result_rejects_missing_cards():
    board = BoardData(
        columns=[Column(id="col-1", title="Todo", cardIds=["missing-card"])],
        cards={},
    )
    result = AIChatResult(reply="Updated", board=board)

    with pytest.raises(ValueError, match="missing cards"):
        _apply_ai_result("dummy-id", "user", result)


def test_apply_ai_result_rejects_multiple_missing_cards():
    """Multiple missing card references are all reported."""
    board = BoardData(
        columns=[Column(id="col-1", title="Todo", cardIds=["ghost-1", "ghost-2"])],
        cards={},
    )
    result = AIChatResult(reply="Updated", board=board)

    with pytest.raises(ValueError, match="ghost-1"):
        _apply_ai_result("dummy-id", "user", result)
