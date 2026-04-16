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
  detail?: string;
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

// ---------------------------------------------------------------------------
// Board
// ---------------------------------------------------------------------------

export const fetchBoard = async (username: string): Promise<BoardData> => {
  const response = await fetch(`/api/board/${username}`, {
    headers: getAuthHeaders(),
  });
  return readJson<BoardData>(response);
};

export const saveBoard = async (
  username: string,
  board: BoardData
): Promise<BoardData> => {
  const response = await fetch(`/api/board/${username}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify(board),
  });
  return readJson<BoardData>(response);
};

// ---------------------------------------------------------------------------
// AI chat (username no longer in request body — comes from JWT on backend)
// ---------------------------------------------------------------------------

export const sendChatMessage = async (
  message: string,
  history: ChatMessage[]
): Promise<AIChatResponse> => {
  const response = await fetch("/api/ai/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify({ message, history }),
  });
  return readJson<AIChatResponse>(response);
};
