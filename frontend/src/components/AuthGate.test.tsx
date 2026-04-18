import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthGate } from "@/components/AuthGate";
import { initialData } from "@/lib/kanban";
import { vi } from "vitest";

const MOCK_BOARDS = [
  { id: "board-1", title: "My Board", created_at: "2026-01-01", updated_at: "2026-01-01" },
];

const signIn = async (username: string, password: string) => {
  await userEvent.type(screen.getByLabelText(/username/i), username);
  // Only type in the first password field (login mode has one, register mode has two)
  const passwordFields = screen.getAllByLabelText(/^password$/i);
  await userEvent.type(passwordFields[0], password);
  await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
};

describe("AuthGate", () => {
  /**
   * Build a fetch mock that handles:
   * - POST /api/auth/login  — validates demo credentials
   * - POST /api/auth/register — always succeeds
   * - GET  /api/boards      — returns MOCK_BOARDS
   * - GET  /api/boards/:id  — returns boardData
   * - PUT  /api/boards/:id  — returns boardData
   */
  const makeFetch = (boardData: unknown) => {
    return vi.fn().mockImplementation((url: string, options?: RequestInit) => {
      if (typeof url !== "string") {
        return Promise.resolve({ ok: false, status: 400, json: async () => ({}) });
      }

      if (url.includes("/api/auth/login")) {
        const body = options?.body ? JSON.parse(options.body as string) : {};
        if (body.username === "user" && body.password === "password") {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({ access_token: "test-token", username: "user", token_type: "bearer" }),
          });
        }
        return Promise.resolve({
          ok: false,
          status: 401,
          json: async () => ({ detail: "Invalid credentials" }),
        });
      }

      if (url.includes("/api/auth/register")) {
        return Promise.resolve({
          ok: true,
          status: 201,
          json: async () => ({ username: "newuser", message: "Account created successfully" }),
        });
      }

      // GET /api/boards (list)
      if (url === "/api/boards" && (!options?.method || options.method === "GET")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ boards: MOCK_BOARDS }),
        });
      }

      // POST /api/boards (create)
      if (url === "/api/boards" && options?.method === "POST") {
        const body = options?.body ? JSON.parse(options.body as string) : {};
        return Promise.resolve({
          ok: true,
          status: 201,
          json: async () => ({
            id: "board-new",
            title: body.title ?? "New Board",
            created_at: "2026-01-01",
            updated_at: "2026-01-01",
          }),
        });
      }

      // Stats endpoint
      if (url.includes("/stats")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            board_id: "board-1",
            total_cards: 0,
            overdue_count: 0,
            columns: [],
            priority_breakdown: { low: 0, medium: 0, high: 0, urgent: 0, none: 0 },
          }),
        });
      }

      // Activity endpoint
      if (url.includes("/activity")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ board_id: "board-1", entries: [] }),
        });
      }

      // Board data endpoints
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => boardData,
      });
    });
  };

  beforeEach(() => {
    sessionStorage.clear();
    global.fetch = makeFetch(initialData) as typeof fetch;
  });

  it("shows the login form by default", () => {
    render(<AuthGate />);
    expect(screen.getByRole("heading", { name: /sign in/i })).toBeInTheDocument();
  });

  it("shows sign up link on login form", () => {
    render(<AuthGate />);
    expect(screen.getByRole("button", { name: /sign up/i })).toBeInTheDocument();
  });

  it("switches to register form when sign up is clicked", async () => {
    render(<AuthGate />);
    await userEvent.click(screen.getByRole("button", { name: /sign up/i }));
    expect(screen.getByRole("heading", { name: /create account/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
  });

  it("switches back to login from register", async () => {
    render(<AuthGate />);
    await userEvent.click(screen.getByRole("button", { name: /sign up/i }));
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(screen.getByRole("heading", { name: /sign in/i })).toBeInTheDocument();
  });

  it("rejects invalid credentials", async () => {
    render(<AuthGate />);
    await signIn("user", "wrong");
    expect(await screen.findByText(/invalid credentials/i)).toBeInTheDocument();
  });

  it("allows login with the demo credentials", async () => {
    render(<AuthGate />);
    await signIn("user", "password");
    // After login we see the top bar with the username and logout button
    expect(await screen.findByRole("button", { name: /log out/i })).toBeInTheDocument();
    expect(screen.getByText("user")).toBeInTheDocument();
  });

  it("logs out and returns to the login screen", async () => {
    render(<AuthGate />);
    await signIn("user", "password");
    await userEvent.click(await screen.findByRole("button", { name: /log out/i }));
    expect(screen.getByRole("heading", { name: /sign in/i })).toBeInTheDocument();
  });

  it("renders board data from the API", async () => {
    const apiBoard = {
      ...initialData,
      columns: [{ id: "col-a", title: "API Column", cardIds: ["card-1"] }],
    };
    global.fetch = makeFetch(apiBoard) as typeof fetch;

    render(<AuthGate />);
    await signIn("user", "password");
    expect(await screen.findByText("API Column")).toBeInTheDocument();
  });

  it("shows empty-state create button when user has no boards", async () => {
    global.fetch = vi.fn().mockImplementation((url: string, options?: RequestInit) => {
      if (url.includes("/api/auth/login")) {
        const body = options?.body ? JSON.parse(options.body as string) : {};
        if (body.username === "user" && body.password === "password") {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({ access_token: "test-token", username: "user", token_type: "bearer" }),
          });
        }
      }
      // Return empty boards list
      if (url === "/api/boards") {
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ boards: [] }) });
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    }) as typeof fetch;

    render(<AuthGate />);
    await signIn("user", "password");
    expect(await screen.findByRole("button", { name: /create board/i })).toBeInTheDocument();
  });
});
