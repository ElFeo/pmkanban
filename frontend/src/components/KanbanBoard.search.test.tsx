import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { KanbanBoard } from "@/components/KanbanBoard";
import type { BoardData } from "@/lib/kanban";

const makeBoard = (): BoardData => ({
  columns: [
    { id: "col-1", title: "Todo", cardIds: ["card-1", "card-2"] },
    { id: "col-2", title: "Done", cardIds: ["card-3"] },
  ],
  cards: {
    "card-1": { id: "card-1", title: "Fix login bug", details: "auth issue", labels: ["bug"] },
    "card-2": { id: "card-2", title: "Design homepage", details: "mockup needed", labels: [] },
    "card-3": { id: "card-3", title: "Deploy release", details: "v2 production push", labels: ["infra"] },
  },
});

describe("KanbanBoard search", () => {
  it("renders the search input", () => {
    render(<KanbanBoard board={makeBoard()} onBoardChange={vi.fn()} />);
    expect(screen.getByLabelText("Search cards")).toBeTruthy();
  });

  it("filters cards by title match", () => {
    render(<KanbanBoard board={makeBoard()} onBoardChange={vi.fn()} />);
    const search = screen.getByLabelText("Search cards");
    fireEvent.change(search, { target: { value: "login" } });
    expect(screen.getByText("Fix login bug")).toBeTruthy();
    expect(screen.queryByText("Design homepage")).toBeNull();
    expect(screen.queryByText("Deploy release")).toBeNull();
  });

  it("filters by details match", () => {
    render(<KanbanBoard board={makeBoard()} onBoardChange={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Search cards"), { target: { value: "mockup" } });
    expect(screen.getByText("Design homepage")).toBeTruthy();
    expect(screen.queryByText("Fix login bug")).toBeNull();
  });

  it("filters by label match", () => {
    render(<KanbanBoard board={makeBoard()} onBoardChange={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Search cards"), { target: { value: "infra" } });
    expect(screen.getByText("Deploy release")).toBeTruthy();
    expect(screen.queryByText("Fix login bug")).toBeNull();
  });

  it("shows all cards when search is cleared", () => {
    render(<KanbanBoard board={makeBoard()} onBoardChange={vi.fn()} />);
    const search = screen.getByLabelText("Search cards");
    fireEvent.change(search, { target: { value: "login" } });
    fireEvent.change(search, { target: { value: "" } });
    expect(screen.getByText("Fix login bug")).toBeTruthy();
    expect(screen.getByText("Design homepage")).toBeTruthy();
    expect(screen.getByText("Deploy release")).toBeTruthy();
  });

  it("shows Clear filters button when query is non-empty", () => {
    render(<KanbanBoard board={makeBoard()} onBoardChange={vi.fn()} />);
    expect(screen.queryByText("Clear filters")).toBeNull();
    fireEvent.change(screen.getByLabelText("Search cards"), { target: { value: "x" } });
    expect(screen.getByText("Clear filters")).toBeTruthy();
  });

  it("Export JSON button is present", () => {
    render(<KanbanBoard board={makeBoard()} onBoardChange={vi.fn()} />);
    expect(screen.getByLabelText("Export board as JSON")).toBeTruthy();
  });
});
