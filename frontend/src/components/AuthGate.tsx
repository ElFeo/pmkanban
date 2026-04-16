"use client";

import { useEffect, useState, type FormEvent } from "react";
import { ChatSidebar } from "@/components/ChatSidebar";
import { KanbanBoard } from "@/components/KanbanBoard";
import {
  fetchBoard,
  login,
  saveBoard,
  sendChatMessage,
  setAuthToken,
  type ChatMessage,
} from "@/lib/api";
import { initialData, type BoardData } from "@/lib/kanban";

const AUTH_TOKEN_KEY = "pm-token";
const AUTH_USERNAME_KEY = "pm-username";

const initialFormState = { username: "", password: "" };

type AuthState = "checking" | "authenticated" | "unauthenticated";

export const AuthGate = () => {
  const [authState, setAuthState] = useState<AuthState>("checking");
  const [loggedInUsername, setLoggedInUsername] = useState<string | null>(null);
  const [formState, setFormState] = useState(initialFormState);
  const [error, setError] = useState<string | null>(null);
  const [board, setBoard] = useState<BoardData | null>(null);
  const [loadingBoard, setLoadingBoard] = useState(false);
  const [savingBoard, setSavingBoard] = useState(false);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [chatSending, setChatSending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);

  // Restore session from sessionStorage on mount
  useEffect(() => {
    const token = sessionStorage.getItem(AUTH_TOKEN_KEY);
    const username = sessionStorage.getItem(AUTH_USERNAME_KEY);
    if (token && username) {
      setAuthToken(token);
      setLoggedInUsername(username);
      setAuthState("authenticated");
    } else {
      setAuthState("unauthenticated");
    }
  }, []);

  // Load board after authentication
  useEffect(() => {
    if (authState !== "authenticated" || !loggedInUsername) {
      return;
    }

    setLoadingBoard(true);
    setError(null);
    fetchBoard(loggedInUsername)
      .then((data) => {
        setBoard(data);
      })
      .catch(() => {
        setBoard(initialData);
        setError("Unable to load the board. Showing local data.");
      })
      .finally(() => {
        setLoadingBoard(false);
      });
  }, [authState, loggedInUsername]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const username = formState.username.trim();
    const password = formState.password.trim();

    try {
      const { access_token } = await login(username, password);
      setAuthToken(access_token);
      sessionStorage.setItem(AUTH_TOKEN_KEY, access_token);
      sessionStorage.setItem(AUTH_USERNAME_KEY, username);
      setLoggedInUsername(username);
      setError(null);
      setAuthState("authenticated");
      setFormState(initialFormState);
    } catch {
      setError("Invalid credentials. Please try again.");
    }
  };

  const handleLogout = () => {
    sessionStorage.removeItem(AUTH_TOKEN_KEY);
    sessionStorage.removeItem(AUTH_USERNAME_KEY);
    setAuthToken(null);
    setLoggedInUsername(null);
    setAuthState("unauthenticated");
    setBoard(null);
    setError(null);
    setChatHistory([]);
    setChatError(null);
  };

  const handleBoardChange = (nextBoard: BoardData) => {
    const prevBoard = board;
    setBoard(nextBoard);
    setSavingBoard(true);
    saveBoard(loggedInUsername!, nextBoard)
      .then((saved) => {
        setBoard(saved);
        setError(null);
      })
      .catch(() => {
        setBoard(prevBoard);
        setError("Unable to save changes. Try again.");
      })
      .finally(() => {
        setSavingBoard(false);
      });
  };

  const handleSendChat = async (message: string) => {
    if (!board || chatSending) {
      return;
    }

    const nextHistory: ChatMessage[] = [
      ...chatHistory,
      { role: "user", content: message },
    ];
    setChatHistory(nextHistory);
    setChatSending(true);
    setChatError(null);

    try {
      const response = await sendChatMessage(message, chatHistory);
      setChatHistory((prev) => [
        ...prev,
        { role: "assistant", content: response.reply },
      ]);
      if (response.applied && response.board) {
        setBoard(response.board);
        setError(null);
      }
    } catch (err) {
      const fallback = err instanceof Error ? err.message : "Unable to reach AI.";
      setChatError(fallback);
    } finally {
      setChatSending(false);
    }
  };

  if (authState === "checking") {
    return (
      <div className="min-h-screen bg-[var(--surface)] px-6 py-16 text-center text-sm text-[var(--gray-text)]">
        Loading...
      </div>
    );
  }

  if (authState === "authenticated") {
    return (
      <div className="relative">
        <div className="pointer-events-none fixed right-6 top-6 z-50">
          <button
            type="button"
            onClick={handleLogout}
            className="pointer-events-auto rounded-full border border-[var(--stroke)] bg-white px-4 py-2 text-xs font-semibold uppercase tracking-wide text-[var(--navy-dark)] shadow-[var(--shadow)] transition hover:border-[var(--primary-blue)]"
          >
            Log out
          </button>
        </div>
        {error ? (
          <div className="absolute left-0 right-0 top-0 z-40 mx-auto max-w-[520px] px-6 pt-6">
            <div className="rounded-2xl border border-[var(--stroke)] bg-white/90 p-4 text-sm text-[var(--secondary-purple)] shadow-[var(--shadow)]">
              {error}
            </div>
          </div>
        ) : null}
        {loadingBoard || !board ? (
          <div className="min-h-screen bg-[var(--surface)] px-6 py-16 text-center text-sm text-[var(--gray-text)]">
            Loading board...
          </div>
        ) : (
          <div className="mx-auto grid max-w-[1600px] grid-cols-1 gap-6 px-6 pb-16 pt-12 xl:grid-cols-[1fr_360px]">
            <KanbanBoard board={board} onBoardChange={handleBoardChange} />
            <ChatSidebar
              messages={chatHistory}
              onSend={handleSendChat}
              isSending={chatSending}
              error={chatError}
            />
          </div>
        )}
        {savingBoard ? (
          <div className="fixed bottom-6 right-6 z-50 rounded-full border border-[var(--stroke)] bg-white px-4 py-2 text-xs font-semibold uppercase tracking-wide text-[var(--gray-text)] shadow-[var(--shadow)]">
            Saving...
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className="relative min-h-screen overflow-hidden">
      <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

      <main className="relative mx-auto flex min-h-screen max-w-[520px] items-center px-6">
        <div className="w-full rounded-[28px] border border-[var(--stroke)] bg-white/90 p-10 shadow-[var(--shadow)] backdrop-blur">
          <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
            Project Management MVP
          </p>
          <h1 className="mt-4 font-display text-3xl font-semibold text-[var(--navy-dark)]">
            Sign in
          </h1>
          <p className="mt-3 text-sm leading-6 text-[var(--gray-text)]">
            Use the demo credentials to access your Kanban workspace.
          </p>

          <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
            <label className="block text-xs font-semibold uppercase tracking-wide text-[var(--gray-text)]">
              Username
              <input
                value={formState.username}
                onChange={(event) =>
                  setFormState((prev) => ({
                    ...prev,
                    username: event.target.value,
                  }))
                }
                className="mt-2 w-full rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm font-medium text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
                aria-label="Username"
                autoComplete="username"
                maxLength={100}
                required
              />
            </label>
            <label className="block text-xs font-semibold uppercase tracking-wide text-[var(--gray-text)]">
              Password
              <input
                value={formState.password}
                onChange={(event) =>
                  setFormState((prev) => ({
                    ...prev,
                    password: event.target.value,
                  }))
                }
                type="password"
                className="mt-2 w-full rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm font-medium text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
                aria-label="Password"
                autoComplete="current-password"
                maxLength={200}
                required
              />
            </label>
            {error ? (
              <p className="text-sm font-semibold text-[var(--secondary-purple)]">
                {error}
              </p>
            ) : null}
            <button
              type="submit"
              className="w-full rounded-full bg-[var(--secondary-purple)] px-4 py-3 text-xs font-semibold uppercase tracking-wide text-white transition hover:brightness-110"
            >
              Sign in
            </button>
          </form>
        </div>
      </main>
    </div>
  );
};
