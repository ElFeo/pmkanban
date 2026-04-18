"use client";

import { useEffect, useState, type FormEvent } from "react";
import { addComment, deleteComment, getComments, type Comment } from "@/lib/api";

type CardCommentsPanelProps = {
  boardId: string;
  cardId: string;
  currentUser: string;
};

export const CardCommentsPanel = ({ boardId, cardId, currentUser }: CardCommentsPanelProps) => {
  const [comments, setComments] = useState<Comment[]>([]);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!boardId || !cardId) return;
    getComments(boardId, cardId).then(setComments).catch(() => null);
  }, [boardId, cardId]);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!draft.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const comment = await addComment(boardId, cardId, draft.trim());
      setComments((prev) => [...prev, comment]);
      setDraft("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to post comment.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (commentId: string) => {
    try {
      await deleteComment(boardId, cardId, commentId);
      setComments((prev) => prev.filter((c) => c.id !== commentId));
    } catch {
      setError("Failed to delete comment.");
    }
  };

  return (
    <div className="mt-6 border-t border-[var(--stroke)] pt-5">
      <p className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
        Comments ({comments.length})
      </p>

      {comments.length > 0 && (
        <div className="mb-4 space-y-3">
          {comments.map((c) => (
            <div key={c.id} className="flex gap-3">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[var(--surface)] text-xs font-semibold text-[var(--navy-dark)]">
                {c.author[0].toUpperCase()}
              </div>
              <div className="flex-1">
                <div className="flex items-baseline gap-2">
                  <span className="text-xs font-semibold text-[var(--navy-dark)]">{c.author}</span>
                  <span className="text-[10px] text-[var(--gray-text)]">{c.created_at.slice(0, 16).replace("T", " ")}</span>
                </div>
                <p className="mt-0.5 text-sm text-[var(--gray-text)]">{c.content}</p>
              </div>
              {c.author === currentUser && (
                <button
                  type="button"
                  onClick={() => handleDelete(c.id)}
                  className="shrink-0 self-start text-[10px] text-[var(--gray-text)] transition hover:text-red-500"
                  aria-label="Delete comment"
                >
                  ×
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Add a comment…"
          className="flex-1 rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
          maxLength={1000}
        />
        <button
          type="submit"
          disabled={saving || !draft.trim()}
          className="rounded-full bg-[var(--secondary-purple)] px-4 py-2 text-xs font-semibold text-white transition hover:brightness-110 disabled:opacity-50"
        >
          Post
        </button>
      </form>
      {error && <p className="mt-2 text-xs text-red-500">{error}</p>}
    </div>
  );
};
