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

type ApiError = {
  message: string;
};

const parseError = (error: unknown) => {
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected error";
};

const readJson = async <T>(response: Response): Promise<T> => {
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const errorBody = (await response.json()) as ApiError;
      if (errorBody?.message) {
        message = errorBody.message;
      }
    } catch {
      // ignore parse errors
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
};

export const fetchBoard = async (username: string): Promise<BoardData> => {
  try {
    const response = await fetch(`/api/board/${username}`);
    return await readJson<BoardData>(response);
  } catch (error) {
    throw new Error(parseError(error));
  }
};

export const saveBoard = async (
  username: string,
  board: BoardData
): Promise<BoardData> => {
  try {
    const response = await fetch(`/api/board/${username}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(board),
    });
    return await readJson<BoardData>(response);
  } catch (error) {
    throw new Error(parseError(error));
  }
};

export const sendChatMessage = async (
  username: string,
  message: string,
  history: ChatMessage[]
): Promise<AIChatResponse> => {
  try {
    const response = await fetch("/api/ai/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        username,
        message,
        history,
      }),
    });
    return await readJson<AIChatResponse>(response);
  } catch (error) {
    throw new Error(parseError(error));
  }
};
