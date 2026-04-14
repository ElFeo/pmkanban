import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { ChatSidebar } from "@/components/ChatSidebar";

describe("ChatSidebar", () => {
  it("renders empty state", () => {
    render(
      <ChatSidebar
        messages={[]}
        onSend={vi.fn()}
        isSending={false}
        error={null}
      />
    );
    expect(screen.getByText(/no messages yet/i)).toBeInTheDocument();
  });

  it("calls onSend with message", async () => {
    const onSend = vi.fn();
    render(
      <ChatSidebar
        messages={[]}
        onSend={onSend}
        isSending={false}
        error={null}
      />
    );

    await userEvent.type(
      screen.getByLabelText(/chat message/i),
      "Rename Backlog to Intake"
    );
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(onSend).toHaveBeenCalledWith("Rename Backlog to Intake");
  });

  it("disables send while sending", () => {
    render(
      <ChatSidebar
        messages={[]}
        onSend={vi.fn()}
        isSending={true}
        error={null}
      />
    );
    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
  });
});
