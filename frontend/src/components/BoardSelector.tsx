"use client";

import { useState } from "react";
import type { BoardSummary } from "@/lib/api";

type Props = {
  boards: BoardSummary[];
  activeBoardId: string;
  onSelect: (boardId: string) => void;
  onCreate: (title: string) => void;
  onRename: (boardId: string, title: string) => void;
  onDelete: (boardId: string) => void;
};

export const BoardSelector = ({
  boards,
  activeBoardId,
  onSelect,
  onCreate,
  onRename,
  onDelete,
}: Props) => {
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");

  const activeBoard = boards.find((b) => b.id === activeBoardId);

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    const title = newTitle.trim();
    if (!title) return;
    onCreate(title);
    setNewTitle("");
    setCreating(false);
    setOpen(false);
  };

  const handleRename = (e: React.FormEvent, boardId: string) => {
    e.preventDefault();
    const title = editTitle.trim();
    if (!title) return;
    onRename(boardId, title);
    setEditingId(null);
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm font-semibold text-[var(--navy-dark)] shadow-[var(--shadow)] transition hover:border-[var(--primary-blue)]"
      >
        <span className="max-w-[180px] truncate">
          {activeBoard?.title ?? "Select board"}
        </span>
        <svg
          width="12"
          height="12"
          viewBox="0 0 12 12"
          fill="none"
          className="text-[var(--gray-text)]"
        >
          <path
            d="M2 4l4 4 4-4"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {open && (
        <div className="absolute left-0 top-full z-50 mt-2 w-72 rounded-2xl border border-[var(--stroke)] bg-white p-2 shadow-[var(--shadow)]">
          {boards.map((board) =>
            editingId === board.id ? (
              <form
                key={board.id}
                onSubmit={(e) => handleRename(e, board.id)}
                className="flex gap-2 px-2 py-1"
              >
                <input
                  autoFocus
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  maxLength={100}
                  className="flex-1 rounded-lg border border-[var(--primary-blue)] px-2 py-1 text-sm outline-none"
                />
                <button
                  type="submit"
                  className="rounded-lg bg-[var(--primary-blue)] px-2 py-1 text-xs font-semibold text-white"
                >
                  Save
                </button>
                <button
                  type="button"
                  onClick={() => setEditingId(null)}
                  className="rounded-lg px-2 py-1 text-xs text-[var(--gray-text)]"
                >
                  ✕
                </button>
              </form>
            ) : (
              <div
                key={board.id}
                className={`group flex items-center justify-between rounded-xl px-3 py-2 ${
                  board.id === activeBoardId
                    ? "bg-[var(--surface)] font-semibold text-[var(--navy-dark)]"
                    : "text-[var(--navy-dark)] hover:bg-[var(--surface)]"
                }`}
              >
                <button
                  type="button"
                  className="flex-1 text-left text-sm"
                  onClick={() => {
                    onSelect(board.id);
                    setOpen(false);
                  }}
                >
                  {board.title}
                </button>
                <div className="flex gap-1 opacity-0 transition group-hover:opacity-100">
                  <button
                    type="button"
                    title="Rename"
                    onClick={() => {
                      setEditingId(board.id);
                      setEditTitle(board.title);
                    }}
                    className="rounded px-1 py-0.5 text-xs text-[var(--gray-text)] hover:text-[var(--primary-blue)]"
                  >
                    ✏
                  </button>
                  {boards.length > 1 && (
                    <button
                      type="button"
                      title="Delete"
                      onClick={() => {
                        if (confirm(`Delete "${board.title}"?`)) {
                          onDelete(board.id);
                          setOpen(false);
                        }
                      }}
                      className="rounded px-1 py-0.5 text-xs text-[var(--gray-text)] hover:text-red-500"
                    >
                      ✕
                    </button>
                  )}
                </div>
              </div>
            )
          )}

          <div className="my-1 border-t border-[var(--stroke)]" />

          {creating ? (
            <form onSubmit={handleCreate} className="flex gap-2 px-2 py-1">
              <input
                autoFocus
                placeholder="Board name"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                maxLength={100}
                className="flex-1 rounded-lg border border-[var(--primary-blue)] px-2 py-1 text-sm outline-none"
              />
              <button
                type="submit"
                className="rounded-lg bg-[var(--primary-blue)] px-2 py-1 text-xs font-semibold text-white"
              >
                Add
              </button>
              <button
                type="button"
                onClick={() => setCreating(false)}
                className="rounded-lg px-2 py-1 text-xs text-[var(--gray-text)]"
              >
                ✕
              </button>
            </form>
          ) : (
            <button
              type="button"
              onClick={() => setCreating(true)}
              className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm text-[var(--primary-blue)] hover:bg-[var(--surface)]"
            >
              <span className="text-base leading-none">+</span> New board
            </button>
          )}
        </div>
      )}
    </div>
  );
};
