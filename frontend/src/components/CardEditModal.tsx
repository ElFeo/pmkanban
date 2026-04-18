"use client";

import { useState, type FormEvent, useEffect } from "react";
import type { Card, Priority } from "@/lib/kanban";

const PRIORITIES: { value: Priority; label: string }[] = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "urgent", label: "Urgent" },
];

type CardEditModalProps = {
  card: Card;
  onSave: (updated: Card) => void;
  onClose: () => void;
};

export const CardEditModal = ({ card, onSave, onClose }: CardEditModalProps) => {
  const [formState, setFormState] = useState({
    title: card.title,
    details: card.details ?? "",
    priority: (card.priority ?? "") as Priority | "",
    due_date: card.due_date ?? "",
    labels: (card.labels ?? []).join(", "),
  });

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!formState.title.trim()) return;
    const labels = formState.labels
      .split(",")
      .map((l) => l.trim())
      .filter(Boolean);
    onSave({
      ...card,
      title: formState.title.trim(),
      details: formState.details.trim(),
      priority: formState.priority || null,
      due_date: formState.due_date || null,
      labels,
    });
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="w-full max-w-lg rounded-[24px] border border-[var(--stroke)] bg-white p-8 shadow-[0_24px_48px_rgba(3,33,71,0.16)]">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="font-display text-lg font-semibold text-[var(--navy-dark)]">Edit Card</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-[var(--stroke)] px-3 py-1 text-xs font-semibold text-[var(--gray-text)] transition hover:text-[var(--navy-dark)]"
          >
            Close
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-[var(--gray-text)]">
              Title
            </label>
            <input
              value={formState.title}
              onChange={(e) => setFormState((p) => ({ ...p, title: e.target.value }))}
              className="w-full rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm font-medium text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
              required
              maxLength={200}
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-[var(--gray-text)]">
              Details
            </label>
            <textarea
              value={formState.details}
              onChange={(e) => setFormState((p) => ({ ...p, details: e.target.value }))}
              rows={3}
              className="w-full resize-none rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm text-[var(--gray-text)] outline-none transition focus:border-[var(--primary-blue)]"
            />
          </div>

          <div className="flex gap-3">
            <div className="flex-1">
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-[var(--gray-text)]">
                Priority
              </label>
              <select
                value={formState.priority}
                onChange={(e) => setFormState((p) => ({ ...p, priority: e.target.value as Priority | "" }))}
                className="w-full rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm text-[var(--gray-text)] outline-none transition focus:border-[var(--primary-blue)]"
              >
                <option value="">None</option>
                {PRIORITIES.map(({ value, label }) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>
            <div className="flex-1">
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-[var(--gray-text)]">
                Due date
              </label>
              <input
                type="date"
                value={formState.due_date}
                onChange={(e) => setFormState((p) => ({ ...p, due_date: e.target.value }))}
                className="w-full rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm text-[var(--gray-text)] outline-none transition focus:border-[var(--primary-blue)]"
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-[var(--gray-text)]">
              Labels (comma-separated)
            </label>
            <input
              value={formState.labels}
              onChange={(e) => setFormState((p) => ({ ...p, labels: e.target.value }))}
              placeholder="bug, frontend, v2"
              className="w-full rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm text-[var(--gray-text)] outline-none transition focus:border-[var(--primary-blue)]"
            />
          </div>

          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              className="flex-1 rounded-full bg-[var(--secondary-purple)] px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-white transition hover:brightness-110"
            >
              Save changes
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-full border border-[var(--stroke)] px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-[var(--gray-text)] transition hover:text-[var(--navy-dark)]"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
