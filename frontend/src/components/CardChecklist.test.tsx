import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CardChecklist } from "@/components/CardChecklist";

const makeItem = (overrides = {}) => ({
  id: "item-1",
  card_id: "card-1",
  text: "Do the thing",
  checked: false,
  position: 0,
  ...overrides,
});

const defaultProps = { boardId: "board-1", cardId: "card-1" };

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ card_id: "card-1", items: [makeItem()] }),
  }));
});

describe("CardChecklist", () => {
  it("loads and shows existing items", async () => {
    render(<CardChecklist {...defaultProps} />);
    await waitFor(() => expect(screen.getByText("Do the thing")).toBeTruthy());
  });

  it("shows progress counter in header", async () => {
    render(<CardChecklist {...defaultProps} />);
    await waitFor(() => screen.getByText(/Checklist \(0\/1\)/i));
  });

  it("shows 0/0 when no items", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ card_id: "card-1", items: [] }),
    }));
    render(<CardChecklist {...defaultProps} />);
    await waitFor(() => screen.getByText(/Checklist \(0\/0\)/i));
  });

  it("Add button is disabled when input is empty", () => {
    render(<CardChecklist {...defaultProps} />);
    expect(screen.getByText("Add")).toBeDisabled();
  });

  it("enables Add button when text is typed", () => {
    render(<CardChecklist {...defaultProps} />);
    fireEvent.change(screen.getByPlaceholderText("Add checklist item…"), { target: { value: "New step" } });
    expect(screen.getByText("Add")).not.toBeDisabled();
  });

  it("adds a new item and appends it to the list", async () => {
    const newItem = makeItem({ id: "item-2", text: "New step", position: 1 });
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ card_id: "card-1", items: [] }) })
      .mockResolvedValueOnce({ ok: true, json: async () => newItem });
    vi.stubGlobal("fetch", fetchMock);
    render(<CardChecklist {...defaultProps} />);
    await waitFor(() => screen.getByText(/Checklist \(0\/0\)/i));

    fireEvent.change(screen.getByPlaceholderText("Add checklist item…"), { target: { value: "New step" } });
    fireEvent.click(screen.getByText("Add"));
    await waitFor(() => screen.getByText("New step"));
    expect(screen.getByText(/Checklist \(0\/1\)/i)).toBeTruthy();
  });

  it("toggles an item checked and updates progress", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ card_id: "card-1", items: [makeItem()] }) })
      .mockResolvedValueOnce({ ok: true, json: async () => makeItem({ checked: true }) });
    vi.stubGlobal("fetch", fetchMock);
    render(<CardChecklist {...defaultProps} />);
    await waitFor(() => screen.getByText("Do the thing"));

    const checkbox = screen.getByLabelText("Toggle: Do the thing");
    fireEvent.click(checkbox);
    await waitFor(() => screen.getByText(/Checklist \(1\/1\)/i));
  });

  it("deletes an item when × is clicked", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ card_id: "card-1", items: [makeItem()] }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({}) });
    vi.stubGlobal("fetch", fetchMock);
    render(<CardChecklist {...defaultProps} />);
    await waitFor(() => screen.getByText("Do the thing"));

    fireEvent.click(screen.getByLabelText("Delete checklist item: Do the thing"));
    await waitFor(() => expect(screen.queryByText("Do the thing")).toBeNull());
  });
});
