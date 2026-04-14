import json

import pytest

from app.main import _apply_ai_result, _parse_ai_content
from app.schemas import AIChatResult, BoardData, Card, Column


def _sample_board() -> BoardData:
    return BoardData(
        columns=[Column(id="col-1", title="Todo", cardIds=["card-1"])],
        cards={"card-1": Card(id="card-1", title="Test", details="Details")},
    )


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


def test_parse_ai_content_rejects_missing_reply():
    content = json.dumps({"board": _sample_board().model_dump()})

    with pytest.raises(ValueError, match="schema"):
        _parse_ai_content(content)


def test_apply_ai_result_updates_board(tmp_path, monkeypatch):
    db_path = tmp_path / "ai.db"
    monkeypatch.setenv("PM_DB_PATH", str(db_path))

    result = AIChatResult(reply="Updated", board=_sample_board())

    board, applied = _apply_ai_result("user", result)

    assert applied is True
    assert board is not None
    assert board.cards["card-1"].title == "Test"


def test_apply_ai_result_no_update():
    result = AIChatResult(reply="No changes", board=None)

    board, applied = _apply_ai_result("user", result)

    assert applied is False
    assert board is None


def test_apply_ai_result_rejects_missing_cards():
    board = BoardData(
        columns=[Column(id="col-1", title="Todo", cardIds=["missing-card"])],
        cards={},
    )
    result = AIChatResult(reply="Updated", board=board)

    with pytest.raises(ValueError, match="missing cards"):
        _apply_ai_result("user", result)
