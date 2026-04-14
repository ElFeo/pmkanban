"use client";

import { useState, type FormEvent } from "react";
import clsx from "clsx";
import type { ChatMessage } from "@/lib/api";

type ChatSidebarProps = {
  messages: ChatMessage[];
  onSend: (message: string) => Promise<void> | void;
  isSending: boolean;
  error: string | null;
};

export const ChatSidebar = ({
  messages,
  onSend,
  isSending,
  error,
}: ChatSidebarProps) => {
  const [draft, setDraft] = useState("");

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = draft.trim();
    if (!trimmed) {
      return;
    }
    onSend(trimmed);
    setDraft("");
  };

  return (
    <aside className="flex w-full flex-col rounded-[28px] border border-[var(--stroke)] bg-white/90 p-6 shadow-[var(--shadow)] backdrop-blur">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
            Assistant
          </p>
          <h2 className="mt-2 font-display text-2xl font-semibold text-[var(--navy-dark)]">
            AI chat
          </h2>
          <p className="mt-2 text-sm leading-6 text-[var(--gray-text)]">
            Ask for quick edits. The assistant can move cards, rename columns, and
            keep the board in sync.
          </p>
        </div>
        <div className="rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-4 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--navy-dark)]">
          Live
        </div>
      </div>

      <div className="mt-6 flex flex-1 flex-col gap-3 overflow-hidden">
        <div className="flex min-h-[220px] flex-1 flex-col gap-3 overflow-y-auto rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] p-4">
          {messages.length === 0 ? (
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
              No messages yet
            </p>
          ) : (
            messages.map((message, index) => (
              <div
                key={`${message.role}-${index}`}
                className={clsx(
                  "rounded-2xl px-4 py-3 text-sm leading-6",
                  message.role === "user"
                    ? "self-end bg-[var(--primary-blue)] text-white"
                    : "self-start border border-[var(--stroke)] bg-white text-[var(--navy-dark)]"
                )}
              >
                <span className="block text-[10px] font-semibold uppercase tracking-[0.2em] opacity-70">
                  {message.role === "user" ? "You" : "AI"}
                </span>
                <p className="mt-2 whitespace-pre-line">{message.content}</p>
              </div>
            ))
          )}
        </div>
        {error ? (
          <p className="text-sm font-semibold text-[var(--secondary-purple)]">
            {error}
          </p>
        ) : null}
      </div>

      <form className="mt-4 space-y-3" onSubmit={handleSubmit}>
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Ask the assistant to update your board..."
          rows={3}
          className="w-full resize-none rounded-2xl border border-[var(--stroke)] bg-white px-4 py-3 text-sm text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
          aria-label="Chat message"
        />
        <div className="flex items-center justify-between gap-4">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
            {isSending ? "Sending..." : "Ready"}
          </p>
          <button
            type="submit"
            disabled={isSending || draft.trim().length === 0}
            className="rounded-full bg-[var(--secondary-purple)] px-4 py-2 text-xs font-semibold uppercase tracking-wide text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Send
          </button>
        </div>
      </form>
    </aside>
  );
};
