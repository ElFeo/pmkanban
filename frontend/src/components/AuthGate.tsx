"use client";

import { useEffect, useState, type FormEvent } from "react";
import { BoardSelector } from "@/components/BoardSelector";
import { BoardStatsPanel } from "@/components/BoardStatsPanel";
import { ChatSidebar } from "@/components/ChatSidebar";
import { KanbanBoard } from "@/components/KanbanBoard";
import { UserProfileModal } from "@/components/UserProfileModal";
import {
  createBoard,
  deleteBoard,
  fetchBoard,
  listBoards,
  login,
  register,
  renameBoard,
  saveBoard,
  sendChatMessage,
  setAuthToken,
  type BoardSummary,
  type ChatMessage,
} from "@/lib/api";
import { initialData, type BoardData } from "@/lib/kanban";

const AUTH_TOKEN_KEY = "pm-token";
const AUTH_USERNAME_KEY = "pm-username";

const initialFormState = { username: "", password: "", confirmPassword: "" };

type AuthState = "checking" | "authenticated" | "unauthenticated";
type FormMode = "login" | "register";

export const AuthGate = () => {
  const [authState, setAuthState] = useState<AuthState>("checking");
  const [loggedInUsername, setLoggedInUsername] = useState<string | null>(null);
  const [formMode, setFormMode] = useState<FormMode>("login");
  const [formState, setFormState] = useState(initialFormState);
  const [error, setError] = useState<string | null>(null);
  const [boards, setBoards] = useState<BoardSummary[]>([]);
  const [activeBoardId, setActiveBoardId] = useState<string | null>(null);
  const [board, setBoard] = useState<BoardData | null>(null);
  const [loadingBoard, setLoadingBoard] = useState(false);
  const [savingBoard, setSavingBoard] = useState(false);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [chatSending, setChatSending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [showProfile, setShowProfile] = useState(false);
  const [statsRefreshKey, setStatsRefreshKey] = useState(0);

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

  // Load boards after authentication
  useEffect(() => {
    if (authState !== "authenticated" || !loggedInUsername) {
      return;
    }

    listBoards()
      .then((fetched) => {
        setBoards(fetched);
        if (fetched.length > 0) {
          setActiveBoardId(fetched[0].id);
        }
      })
      .catch(() => {
        setError("Unable to load boards.");
      });
  }, [authState, loggedInUsername]);

  // Load board data when active board changes
  useEffect(() => {
    if (!activeBoardId) return;

    setLoadingBoard(true);
    setError(null);
    fetchBoard(activeBoardId)
      .then((data) => {
        setBoard(data);
        setChatHistory([]);
      })
      .catch(() => {
        setBoard(initialData);
        setError("Unable to load the board. Showing local data.");
      })
      .finally(() => {
        setLoadingBoard(false);
      });
  }, [activeBoardId]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const username = formState.username.trim();
    const password = formState.password.trim();
    setError(null);

    if (formMode === "register") {
      if (password !== formState.confirmPassword) {
        setError("Passwords do not match.");
        return;
      }
      if (password.length < 8) {
        setError("Password must be at least 8 characters.");
        return;
      }
      try {
        await register(username, password);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Registration failed.");
        return;
      }
    }

    try {
      const { access_token } = await login(username, password);
      setAuthToken(access_token);
      sessionStorage.setItem(AUTH_TOKEN_KEY, access_token);
      sessionStorage.setItem(AUTH_USERNAME_KEY, username);
      setLoggedInUsername(username);
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
    setBoards([]);
    setActiveBoardId(null);
    setBoard(null);
    setError(null);
    setChatHistory([]);
    setChatError(null);
  };

  const handleBoardChange = (nextBoard: BoardData) => {
    if (!activeBoardId) return;
    const prevBoard = board;
    setBoard(nextBoard);
    setSavingBoard(true);
    saveBoard(activeBoardId, nextBoard)
      .then((saved) => {
        setBoard(saved);
        setError(null);
        setStatsRefreshKey((k) => k + 1);
      })
      .catch(() => {
        setBoard(prevBoard);
        setError("Unable to save changes. Try again.");
      })
      .finally(() => {
        setSavingBoard(false);
      });
  };

  const handleSelectBoard = (boardId: string) => {
    setActiveBoardId(boardId);
  };

  const handleCreateBoard = async (title: string) => {
    try {
      const newBoard = await createBoard(title);
      setBoards((prev) => [...prev, newBoard]);
      setActiveBoardId(newBoard.id);
    } catch {
      setError("Could not create board.");
    }
  };

  const handleRenameBoard = async (boardId: string, title: string) => {
    try {
      const updated = await renameBoard(boardId, title);
      setBoards((prev) => prev.map((b) => (b.id === boardId ? updated : b)));
    } catch {
      setError("Could not rename board.");
    }
  };

  const handleDeleteBoard = async (boardId: string) => {
    try {
      await deleteBoard(boardId);
      const remaining = boards.filter((b) => b.id !== boardId);
      setBoards(remaining);
      if (activeBoardId === boardId) {
        setActiveBoardId(remaining.length > 0 ? remaining[0].id : null);
        setBoard(null);
      }
    } catch {
      setError("Could not delete board.");
    }
  };

  const handleSendChat = async (message: string) => {
    if (!board || chatSending || !activeBoardId) {
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
      const response = await sendChatMessage(message, chatHistory, activeBoardId);
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
    const hasBoards = boards.length > 0;

    return (
      <div className="relative">
        {showProfile && loggedInUsername && (
          <UserProfileModal
            username={loggedInUsername}
            onClose={() => setShowProfile(false)}
          />
        )}
        {/* Top bar */}
        <div className="fixed left-0 right-0 top-0 z-50 flex items-center justify-between border-b border-[var(--stroke)] bg-white/90 px-6 py-3 backdrop-blur">
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
              PM App
            </span>
            {hasBoards && activeBoardId && (
              <BoardSelector
                boards={boards}
                activeBoardId={activeBoardId}
                onSelect={handleSelectBoard}
                onCreate={handleCreateBoard}
                onRename={handleRenameBoard}
                onDelete={handleDeleteBoard}
              />
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setShowProfile(true)}
              className="rounded-full border border-[var(--stroke)] bg-white px-4 py-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--navy-dark)] shadow-[var(--shadow)] transition hover:border-[var(--primary-blue)]"
            >
              {loggedInUsername}
            </button>
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-full border border-[var(--stroke)] bg-white px-4 py-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--navy-dark)] shadow-[var(--shadow)] transition hover:border-[var(--primary-blue)]"
            >
              Log out
            </button>
          </div>
        </div>

        {error ? (
          <div className="fixed left-0 right-0 top-14 z-40 mx-auto max-w-[520px] px-6 pt-2">
            <div className="rounded-2xl border border-[var(--stroke)] bg-white/90 p-4 text-sm text-[var(--secondary-purple)] shadow-[var(--shadow)]">
              {error}
            </div>
          </div>
        ) : null}

        <div className="pt-14">
          {!hasBoards ? (
            <div className="flex min-h-[calc(100vh-56px)] flex-col items-center justify-center gap-4 text-[var(--gray-text)]">
              <p className="text-sm">No boards yet. Create your first board.</p>
              <button
                type="button"
                onClick={() => handleCreateBoard("My Board")}
                className="rounded-full bg-[var(--primary-blue)] px-6 py-2 text-sm font-semibold text-white transition hover:brightness-110"
              >
                Create board
              </button>
            </div>
          ) : loadingBoard || !board || !activeBoardId ? (
            <div className="flex min-h-[calc(100vh-56px)] items-center justify-center text-sm text-[var(--gray-text)]">
              Loading board...
            </div>
          ) : (
            <div className="mx-auto grid max-w-[1600px] grid-cols-1 gap-6 px-6 pb-16 pt-6 xl:grid-cols-[1fr_340px]">
              <KanbanBoard board={board} boardId={activeBoardId} currentUser={loggedInUsername ?? ""} onBoardChange={handleBoardChange} />
              <div className="flex flex-col gap-4">
                <BoardStatsPanel boardId={activeBoardId} refreshKey={statsRefreshKey} />
                <ChatSidebar
                  messages={chatHistory}
                  onSend={handleSendChat}
                  isSending={chatSending}
                  error={chatError}
                />
              </div>
            </div>
          )}
        </div>

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
            Project Management
          </p>
          <h1 className="mt-4 font-display text-3xl font-semibold text-[var(--navy-dark)]">
            {formMode === "login" ? "Sign in" : "Create account"}
          </h1>
          <p className="mt-3 text-sm leading-6 text-[var(--gray-text)]">
            {formMode === "login"
              ? "Sign in to access your Kanban workspace."
              : "Register to get your own workspace with multiple boards."}
          </p>

          <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
            <label className="block text-xs font-semibold uppercase tracking-wide text-[var(--gray-text)]">
              Username
              <input
                value={formState.username}
                onChange={(event) =>
                  setFormState((prev) => ({ ...prev, username: event.target.value }))
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
                  setFormState((prev) => ({ ...prev, password: event.target.value }))
                }
                type="password"
                className="mt-2 w-full rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm font-medium text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
                aria-label="Password"
                autoComplete={formMode === "login" ? "current-password" : "new-password"}
                maxLength={200}
                required
              />
            </label>
            {formMode === "register" && (
              <label className="block text-xs font-semibold uppercase tracking-wide text-[var(--gray-text)]">
                Confirm Password
                <input
                  value={formState.confirmPassword}
                  onChange={(event) =>
                    setFormState((prev) => ({ ...prev, confirmPassword: event.target.value }))
                  }
                  type="password"
                  className="mt-2 w-full rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm font-medium text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
                  aria-label="Confirm Password"
                  autoComplete="new-password"
                  maxLength={200}
                  required
                />
              </label>
            )}
            {error ? (
              <p className="text-sm font-semibold text-[var(--secondary-purple)]">
                {error}
              </p>
            ) : null}
            <button
              type="submit"
              className="w-full rounded-full bg-[var(--secondary-purple)] px-4 py-3 text-xs font-semibold uppercase tracking-wide text-white transition hover:brightness-110"
            >
              {formMode === "login" ? "Sign in" : "Create account"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-[var(--gray-text)]">
            {formMode === "login" ? (
              <>
                Don&apos;t have an account?{" "}
                <button
                  type="button"
                  onClick={() => {
                    setFormMode("register");
                    setError(null);
                    setFormState(initialFormState);
                  }}
                  className="font-semibold text-[var(--primary-blue)] hover:underline"
                >
                  Sign up
                </button>
              </>
            ) : (
              <>
                Already have an account?{" "}
                <button
                  type="button"
                  onClick={() => {
                    setFormMode("login");
                    setError(null);
                    setFormState(initialFormState);
                  }}
                  className="font-semibold text-[var(--primary-blue)] hover:underline"
                >
                  Sign in
                </button>
              </>
            )}
          </p>
        </div>
      </main>
    </div>
  );
};
