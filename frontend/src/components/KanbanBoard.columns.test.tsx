import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { KanbanBoard } from "@/components/KanbanBoard";
import type { BoardData } from "@/lib/kanban";

const makeBoard = (): BoardData => ({
  columns: [
    { id: "col-1", title: "Todo", cardIds: [] },
    { id: "col-2", title: "Done", cardIds: [] },
  ],
  cards: {},
});

describe("KanbanBoard column management", () => {
  it("renders Add column button", () => {
    render(<KanbanBoard board={makeBoard()} onBoardChange={vi.fn()} />);
    expect(screen.getByText("+ Add column")).toBeTruthy();
  });

  it("adds a new column when Add column is clicked", () => {
    const onBoardChange = vi.fn();
    render(<KanbanBoard board={makeBoard()} onBoardChange={onBoardChange} />);
    fireEvent.click(screen.getByText("+ Add column"));
    const updated: BoardData = onBoardChange.mock.calls[0][0];
    expect(updated.columns).toHaveLength(3);
    expect(updated.columns[2].title).toBe("New Column");
  });

  it("shows Delete col buttons when there are multiple columns", () => {
    render(<KanbanBoard board={makeBoard()} onBoardChange={vi.fn()} />);
    const deleteBtns = screen.getAllByText("Delete col");
    expect(deleteBtns).toHaveLength(2);
  });

  it("hides Delete col button when only one column", () => {
    const board: BoardData = {
      columns: [{ id: "col-1", title: "Solo", cardIds: [] }],
      cards: {},
    };
    render(<KanbanBoard board={board} onBoardChange={vi.fn()} />);
    expect(screen.queryByText("Delete col")).toBeNull();
  });

  it("deletes a column and its cards when Delete col is clicked", () => {
    const board: BoardData = {
      columns: [
        { id: "col-1", title: "Todo", cardIds: ["card-1"] },
        { id: "col-2", title: "Done", cardIds: [] },
      ],
      cards: { "card-1": { id: "card-1", title: "Task", details: "" } },
    };
    const onBoardChange = vi.fn();
    render(<KanbanBoard board={board} onBoardChange={onBoardChange} />);
    const deleteBtn = screen.getAllByText("Delete col")[0];
    fireEvent.click(deleteBtn);
    const updated: BoardData = onBoardChange.mock.calls[0][0];
    expect(updated.columns).toHaveLength(1);
    expect(updated.columns[0].id).toBe("col-2");
    expect(Object.keys(updated.cards)).not.toContain("card-1");
  });
});
