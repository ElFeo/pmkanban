"use client";

import { useEffect, useState, type FormEvent } from "react";
import {
  addChecklistItem,
  deleteChecklistItem,
  getChecklist,
  updateChecklistItem,
  type ChecklistItem,
} from "@/lib/api";

type Props = { boardId: string; cardId: string };

export const CardChecklist = ({ boardId, cardId }: Props) => {
  const [items, setItems] = useState<ChecklistItem[]>([]);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!boardId || !cardId) return;
    getChecklist(boardId, cardId).then(setItems).catch(() => null);
  }, [boardId, cardId]);

  const done = items.filter((i) => i.checked).length;
  const total = items.length;

  const handleAdd = async (e: FormEvent) => {
    e.preventDefault();
    if (!draft.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const item = await addChecklistItem(boardId, cardId, draft.trim());
      setItems((prev) => [...prev, item]);
      setDraft("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add item.");
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (item: ChecklistItem) => {
    try {
      const updated = await updateChecklistItem(boardId, cardId, item.id, { checked: !item.checked });
      setItems((prev) => prev.map((i) => (i.id === updated.id ? updated : i)));
    } catch {
      setError("Failed to update item.");
    }
  };

  const handleDelete = async (itemId: string) => {
    try {
      await deleteChecklistItem(boardId, cardId, itemId);
      setItems((prev) => prev.filter((i) => i.id !== itemId));
    } catch {
      setError("Failed to delete item.");
    }
  };

  return (
    <div className="mt-6 border-t border-[var(--stroke)] pt-5">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
          Checklist ({done}/{total})
        </p>
        {total > 0 && (
          <div className="flex h-1.5 w-24 overflow-hidden rounded-full bg-[var(--surface)]">
            <div
              className="h-full rounded-full bg-[var(--secondary-purple)] transition-all"
              style={{ width: `${total ? (done / total) * 100 : 0}%` }}
            />
          </div>
        )}
      </div>

      {items.length > 0 && (
        <ul className="mb-3 space-y-1.5">
          {items.map((item) => (
            <li key={item.id} className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={item.checked}
                onChange={() => handleToggle(item)}
                className="h-4 w-4 accent-[var(--secondary-purple)]"
                aria-label={`Toggle: ${item.text}`}
              />
              <span
                className={`flex-1 text-sm ${
                  item.checked ? "text-[var(--gray-text)] line-through" : "text-[var(--navy-dark)]"
                }`}
              >
                {item.text}
              </span>
              <button
                type="button"
                onClick={() => handleDelete(item.id)}
                aria-label={`Delete checklist item: ${item.text}`}
                className="shrink-0 text-[10px] text-[var(--gray-text)] transition hover:text-red-500"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={handleAdd} className="flex gap-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Add checklist item…"
          maxLength={500}
          className="flex-1 rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
        />
        <button
          type="submit"
          disabled={saving || !draft.trim()}
          className="rounded-full bg-[var(--surface)] px-4 py-2 text-xs font-semibold text-[var(--navy-dark)] transition hover:bg-[var(--stroke)] disabled:opacity-50"
        >
          Add
        </button>
      </form>
      {error && <p className="mt-2 text-xs text-red-500">{error}</p>}
    </div>
  );
};
