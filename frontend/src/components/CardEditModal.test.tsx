import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CardEditModal } from "@/components/CardEditModal";
import type { Card } from "@/lib/kanban";

const baseCard: Card = {
  id: "card-1",
  title: "Original title",
  details: "Some details",
  priority: "medium",
  due_date: "2026-12-01",
  labels: ["bug", "frontend"],
};

describe("CardEditModal", () => {
  it("renders with existing card data", () => {
    render(
      <CardEditModal card={baseCard} onSave={vi.fn()} onClose={vi.fn()} />
    );
    expect(screen.getByDisplayValue("Original title")).toBeTruthy();
    expect(screen.getByDisplayValue("Some details")).toBeTruthy();
    expect(screen.getByDisplayValue("bug, frontend")).toBeTruthy();
  });

  it("calls onClose when Cancel is clicked", () => {
    const onClose = vi.fn();
    render(<CardEditModal card={baseCard} onSave={vi.fn()} onClose={onClose} />);
    fireEvent.click(screen.getAllByText("Cancel")[0]);
    expect(onClose).toHaveBeenCalled();
  });

  it("calls onSave with updated values on submit", () => {
    const onSave = vi.fn();
    const onClose = vi.fn();
    render(<CardEditModal card={baseCard} onSave={onSave} onClose={onClose} />);

    const titleInput = screen.getByDisplayValue("Original title");
    fireEvent.change(titleInput, { target: { value: "Updated title" } });

    fireEvent.click(screen.getByText("Save changes"));

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Updated title", id: "card-1" })
    );
    expect(onClose).toHaveBeenCalled();
  });

  it("does not submit with empty title", () => {
    const onSave = vi.fn();
    render(<CardEditModal card={baseCard} onSave={onSave} onClose={vi.fn()} />);
    const titleInput = screen.getByDisplayValue("Original title");
    fireEvent.change(titleInput, { target: { value: "  " } });
    fireEvent.click(screen.getByText("Save changes"));
    expect(onSave).not.toHaveBeenCalled();
  });

  it("parses labels correctly on save", () => {
    const onSave = vi.fn();
    render(<CardEditModal card={{ ...baseCard, labels: [] }} onSave={onSave} onClose={vi.fn()} />);
    const labelsInput = screen.getByPlaceholderText("bug, frontend, v2");
    fireEvent.change(labelsInput, { target: { value: "alpha, beta, gamma" } });
    fireEvent.click(screen.getByText("Save changes"));
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ labels: ["alpha", "beta", "gamma"] })
    );
  });
});
