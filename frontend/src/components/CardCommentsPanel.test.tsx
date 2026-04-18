import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CardCommentsPanel } from "@/components/CardCommentsPanel";

const makeComment = (overrides = {}) => ({
  id: "cmt-1",
  card_id: "card-1",
  author: "alice",
  content: "Hello world",
  created_at: "2026-04-18T10:00:00",
  ...overrides,
});

const defaultProps = {
  boardId: "board-1",
  cardId: "card-1",
  currentUser: "alice",
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ card_id: "card-1", comments: [makeComment()] }),
  }));
});

describe("CardCommentsPanel", () => {
  it("loads and shows existing comments", async () => {
    render(<CardCommentsPanel {...defaultProps} />);
    await waitFor(() => expect(screen.getByText("Hello world")).toBeTruthy());
    expect(screen.getByText("alice")).toBeTruthy();
  });

  it("shows comment count in header", async () => {
    render(<CardCommentsPanel {...defaultProps} />);
    await waitFor(() => screen.getByText(/Comments \(1\)/i));
  });

  it("shows empty list when no comments", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ card_id: "card-1", comments: [] }),
    }));
    render(<CardCommentsPanel {...defaultProps} />);
    await waitFor(() => screen.getByText(/Comments \(0\)/i));
  });

  it("shows delete button only for own comments", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        card_id: "card-1",
        comments: [
          makeComment({ id: "cmt-a", author: "alice", content: "Mine" }),
          makeComment({ id: "cmt-b", author: "bob", content: "Not mine" }),
        ],
      }),
    }));
    render(<CardCommentsPanel {...defaultProps} currentUser="alice" />);
    await waitFor(() => screen.getByText("Mine"));
    const deleteButtons = screen.getAllByLabelText("Delete comment");
    expect(deleteButtons).toHaveLength(1);
  });

  it("post button is disabled when input is empty", () => {
    render(<CardCommentsPanel {...defaultProps} />);
    const postBtn = screen.getByText("Post");
    expect(postBtn).toBeDisabled();
  });

  it("enables post button when comment is typed", () => {
    render(<CardCommentsPanel {...defaultProps} />);
    const input = screen.getByPlaceholderText("Add a comment…");
    fireEvent.change(input, { target: { value: "New comment" } });
    expect(screen.getByText("Post")).not.toBeDisabled();
  });

  it("posts a comment and appends it to the list", async () => {
    const newComment = makeComment({ id: "cmt-2", content: "New comment" });
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ card_id: "card-1", comments: [] }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => newComment,
      });
    vi.stubGlobal("fetch", fetchMock);
    render(<CardCommentsPanel {...defaultProps} />);
    await waitFor(() => screen.getByText(/Comments \(0\)/i));

    const input = screen.getByPlaceholderText("Add a comment…");
    fireEvent.change(input, { target: { value: "New comment" } });
    fireEvent.click(screen.getByText("Post"));

    await waitFor(() => screen.getByText("New comment"));
    expect(screen.getByText(/Comments \(1\)/i)).toBeTruthy();
  });

  it("deletes a comment when delete is clicked", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ card_id: "card-1", comments: [makeComment()] }),
      })
      .mockResolvedValueOnce({ ok: true, json: async () => ({}) });
    vi.stubGlobal("fetch", fetchMock);
    render(<CardCommentsPanel {...defaultProps} />);
    await waitFor(() => screen.getByText("Hello world"));

    fireEvent.click(screen.getByLabelText("Delete comment"));
    await waitFor(() => expect(screen.queryByText("Hello world")).toBeNull());
  });
});
