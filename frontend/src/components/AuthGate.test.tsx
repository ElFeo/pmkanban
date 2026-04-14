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
  const mockFetch = (payload: unknown) => {
    return vi.fn().mockResolvedValue({
      ok: true,
      json: async () => payload,
    });
  };

  beforeEach(() => {
    localStorage.clear();
    global.fetch = mockFetch(initialData) as typeof fetch;
  });

  it("shows the login form by default", () => {
    render(<AuthGate />);
    expect(screen.getByRole("heading", { name: /sign in/i })).toBeInTheDocument();
  });

  it("rejects invalid credentials", async () => {
    render(<AuthGate />);
    await signIn("user", "wrong");
    expect(
      screen.getByText(/invalid credentials/i)
    ).toBeInTheDocument();
  });

  it("allows login with the demo credentials", async () => {
    render(<AuthGate />);
    await signIn("user", "password");
    expect(
      await screen.findByRole("heading", { name: /kanban studio/i })
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /log out/i })).toBeInTheDocument();
  });

  it("logs out and returns to the login screen", async () => {
    render(<AuthGate />);
    await signIn("user", "password");
    await userEvent.click(screen.getByRole("button", { name: /log out/i }));
    expect(
      screen.getByRole("heading", { name: /sign in/i })
    ).toBeInTheDocument();
  });

  it("renders data from the API", async () => {
    const apiBoard = {
      ...initialData,
      columns: [
        { id: "col-a", title: "API Column", cardIds: ["card-1"] },
      ],
    };
    global.fetch = mockFetch(apiBoard) as typeof fetch;

    render(<AuthGate />);
    await signIn("user", "password");
    expect(
      await screen.findByText("API Column")
    ).toBeInTheDocument();
  });
});
