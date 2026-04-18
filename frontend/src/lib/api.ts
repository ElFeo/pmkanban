import type { BoardData } from "@/lib/kanban";

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type AIChatResponse = {
  reply: string;
  board?: BoardData | null;
  applied: boolean;
};

export type LoginResponse = {
  access_token: string;
  username: string;
  token_type: string;
};

export type RegisterResponse = {
  username: string;
  message: string;
};

export type BoardSummary = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type BoardListResponse = {
  boards: BoardSummary[];
};

// ---------------------------------------------------------------------------
// Module-level auth token store
// ---------------------------------------------------------------------------

let _authToken: string | null = null;

export const setAuthToken = (token: string | null): void => {
  _authToken = token;
};

const getAuthHeaders = (): Record<string, string> => {
  if (_authToken) {
    return { Authorization: `Bearer ${_authToken}` };
  }
  return {};
};

// ---------------------------------------------------------------------------
// Response parsing helper
// ---------------------------------------------------------------------------

type ApiError = {
  message?: string;
  detail?: string | { msg: string }[];
};

const readJson = async <T>(response: Response): Promise<T> => {
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const errorBody = (await response.json()) as ApiError;
      if (errorBody?.message) {
        message = errorBody.message;
      } else if (typeof errorBody?.detail === "string") {
        message = errorBody.detail;
      } else if (Array.isArray(errorBody?.detail)) {
        message = errorBody.detail.map((e) => e.msg).join(", ");
      }
    } catch {
      // ignore parse errors on error responses
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
};

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export const login = async (
  username: string,
  password: string
): Promise<LoginResponse> => {
  const response = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  return readJson<LoginResponse>(response);
};

export const register = async (
  username: string,
  password: string
): Promise<RegisterResponse> => {
  const response = await fetch("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  return readJson<RegisterResponse>(response);
};

// ---------------------------------------------------------------------------
// Boards (multi-board)
// ---------------------------------------------------------------------------

export const listBoards = async (): Promise<BoardSummary[]> => {
  const response = await fetch("/api/boards", {
    headers: getAuthHeaders(),
  });
  const data = await readJson<BoardListResponse>(response);
  return data.boards;
};

export const createBoard = async (title: string): Promise<BoardSummary> => {
  const response = await fetch("/api/boards", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify({ title }),
  });
  return readJson<BoardSummary>(response);
};

export const fetchBoard = async (boardId: string): Promise<BoardData> => {
  const response = await fetch(`/api/boards/${boardId}`, {
    headers: getAuthHeaders(),
  });
  return readJson<BoardData>(response);
};

export const saveBoard = async (
  boardId: string,
  board: BoardData
): Promise<BoardData> => {
  const response = await fetch(`/api/boards/${boardId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify(board),
  });
  return readJson<BoardData>(response);
};

export const renameBoard = async (
  boardId: string,
  title: string
): Promise<BoardSummary> => {
  const response = await fetch(`/api/boards/${boardId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify({ title }),
  });
  return readJson<BoardSummary>(response);
};

export const deleteBoard = async (boardId: string): Promise<void> => {
  const response = await fetch(`/api/boards/${boardId}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  if (!response.ok) {
    throw new Error(`Delete failed (${response.status})`);
  }
};

// ---------------------------------------------------------------------------
// Card comments
// ---------------------------------------------------------------------------

export type Comment = {
  id: string;
  card_id: string;
  author: string;
  content: string;
  created_at: string;
};

export const getComments = async (boardId: string, cardId: string): Promise<Comment[]> => {
  const response = await fetch(`/api/boards/${boardId}/cards/${cardId}/comments`, {
    headers: getAuthHeaders(),
  });
  const data = await readJson<{ card_id: string; comments: Comment[] }>(response);
  return data.comments;
};

export const addComment = async (boardId: string, cardId: string, content: string): Promise<Comment> => {
  const response = await fetch(`/api/boards/${boardId}/cards/${cardId}/comments`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify({ content }),
  });
  return readJson<Comment>(response);
};

export const deleteComment = async (boardId: string, cardId: string, commentId: string): Promise<void> => {
  const response = await fetch(`/api/boards/${boardId}/cards/${cardId}/comments/${commentId}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  if (!response.ok) throw new Error(`Delete failed (${response.status})`);
};

// ---------------------------------------------------------------------------
// Board stats + activity
// ---------------------------------------------------------------------------

export type ColumnStats = {
  column_id: string;
  column_title: string;
  card_count: number;
};

export type PriorityBreakdown = {
  low: number;
  medium: number;
  high: number;
  urgent: number;
  none: number;
};

export type BoardStats = {
  board_id: string;
  total_cards: number;
  overdue_count: number;
  columns: ColumnStats[];
  priority_breakdown: PriorityBreakdown;
};

export type ActivityEntry = {
  id: string;
  action: string;
  detail: string;
  created_at: string;
};

export const getBoardStats = async (boardId: string): Promise<BoardStats> => {
  const response = await fetch(`/api/boards/${boardId}/stats`, {
    headers: getAuthHeaders(),
  });
  return readJson<BoardStats>(response);
};

export const getBoardActivity = async (boardId: string): Promise<ActivityEntry[]> => {
  const response = await fetch(`/api/boards/${boardId}/activity`, {
    headers: getAuthHeaders(),
  });
  const data = await readJson<{ board_id: string; entries: ActivityEntry[] }>(response);
  return data.entries;
};

// ---------------------------------------------------------------------------
// User profile
// ---------------------------------------------------------------------------

export type UserProfile = {
  username: string;
  board_count: number;
};

export const getProfile = async (): Promise<UserProfile> => {
  const response = await fetch("/api/me", { headers: getAuthHeaders() });
  return readJson<UserProfile>(response);
};

export const changePassword = async (
  current_password: string,
  new_password: string
): Promise<void> => {
  const response = await fetch("/api/me/password", {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify({ current_password, new_password }),
  });
  if (!response.ok) {
    await readJson<never>(response); // throws with proper message
  }
};

// ---------------------------------------------------------------------------
// AI chat
// ---------------------------------------------------------------------------

export const sendChatMessage = async (
  message: string,
  history: ChatMessage[],
  boardId?: string
): Promise<AIChatResponse> => {
  const response = await fetch("/api/ai/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify({ message, history, board_id: boardId ?? null }),
  });
  return readJson<AIChatResponse>(response);
};
