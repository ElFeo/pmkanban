import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthGate } from "@/components/AuthGate";
import { initialData } from "@/lib/kanban";
import { vi } from "vitest";

const signIn = async (username: string, password: string) => {
  await userEvent.type(screen.getByLabelText(/username/i), username);
  await userEvent.type(screen.getByLabelText(/password/i), password);
  await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
};

describe("AuthGate", () => {
  /**
   * Build a fetch mock that:
   * - Returns a valid JWT response for POST /api/auth/login with correct credentials
   * - Returns 401 for POST /api/auth/login with wrong credentials
   * - Returns boardData for all other requests (board GET/PUT)
   */
  const makeFetch = (boardData: unknown) => {
    return vi.fn().mockImplementation((url: string, options?: RequestInit) => {
      if (typeof url === "string" && url.includes("/api/auth/login")) {
        const body = options?.body ? JSON.parse(options.body as string) : {};
        if (body.username === "user" && body.password === "password") {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({
              access_token: "test-token",
              username: "user",
              token_type: "bearer",
            }),
          });
        }
        return Promise.resolve({
          ok: false,
          status: 401,
          json: async () => ({ detail: "Invalid credentials" }),
        });
      }
      // Board and other endpoints
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

  it("rejects invalid credentials", async () => {
    render(<AuthGate />);
    await signIn("user", "wrong");
    expect(
      await screen.findByText(/invalid credentials/i)
    ).toBeInTheDocument();
  });

  it("allows login with the demo credentials", async () => {
    render(<AuthGate />);
    await signIn("user", "password");
    expect(
      await screen.findByRole("heading", { name: /kanban studio/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /ai chat/i })
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /log out/i })).toBeInTheDocument();
  });

  it("logs out and returns to the login screen", async () => {
    render(<AuthGate />);
    await signIn("user", "password");
    await userEvent.click(await screen.findByRole("button", { name: /log out/i }));
    expect(
      screen.getByRole("heading", { name: /sign in/i })
    ).toBeInTheDocument();
  });

  it("renders data from the API", async () => {
    const apiBoard = {
      ...initialData,
      columns: [{ id: "col-a", title: "API Column", cardIds: ["card-1"] }],
    };
    global.fetch = makeFetch(apiBoard) as typeof fetch;

    render(<AuthGate />);
    await signIn("user", "password");
    expect(await screen.findByText("API Column")).toBeInTheDocument();
  });
});
