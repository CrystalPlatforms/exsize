import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AuthProvider } from "@/auth";
import SettingsPage from "@/pages/SettingsPage";

vi.mock("@/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api")>();
  return {
    ...actual,
    getSubscription: vi.fn(),
    cancelSubscription: vi.fn(),
    getMe: vi.fn(),
    setToken: vi.fn(),
    requestAccountDeletion: vi.fn(),
    deleteOwnAccount: vi.fn(),
    getProfile: vi.fn(),
    setNickname: vi.fn(),
  };
});

const pushState = {
  isSupported: true,
  permission: "default" as NotificationPermission,
  isSubscribed: false,
  error: null as string | null,
  enable: vi.fn(),
  disable: vi.fn(),
};
vi.mock("@/hooks/usePushNotifications", () => ({
  usePushNotifications: () => pushState,
}));

import {
  getSubscription as getSubscriptionMock,
  requestAccountDeletion as requestAccountDeletionMock,
  deleteOwnAccount as deleteOwnAccountMock,
  getProfile as getProfileMock,
  setNickname as setNicknameMock,
} from "@/api";
import type { UserResponse, ProfileResponse } from "@/api";

function renderSettings(role: "parent" | "child" = "parent") {
  const user: UserResponse = {
    id: 1,
    email: `${role}@test.com`,
    role,
    language: "en",
  };
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter>
          <SettingsPage user={user} />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    pushState.isSupported = true;
    pushState.permission = "default";
    pushState.isSubscribed = false;
    pushState.error = null;
    pushState.enable = vi.fn();
    pushState.disable = vi.fn();
  });

  it("shows Free plan status for free users", async () => {
    vi.mocked(getSubscriptionMock).mockResolvedValue({
      plan: "free",
      status: "free",
    });

    renderSettings();

    expect(await screen.findByText("Settings")).toBeInTheDocument();
    expect(await screen.findByText("Subscription")).toBeInTheDocument();
    expect(screen.getByText("Free")).toBeInTheDocument();
  });

  it("shows SizePass plan status for subscribed users", async () => {
    vi.mocked(getSubscriptionMock).mockResolvedValue({
      plan: "sizepass",
      status: "active",
    });

    renderSettings();

    expect(await screen.findByText("SizePass")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("shows upgrade prompt for free users", async () => {
    vi.mocked(getSubscriptionMock).mockResolvedValue({
      plan: "free",
      status: "free",
    });

    renderSettings();

    expect(
      await screen.findByRole("button", { name: /upgrade/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/leaderboards, advanced stats/i),
    ).toBeInTheDocument();
  });

  it("upgrade button links to /sizepass", async () => {
    vi.mocked(getSubscriptionMock).mockResolvedValue({
      plan: "free",
      status: "free",
    });

    renderSettings();

    const link = await screen.findByRole("link", { name: /upgrade/i });
    expect(link).toHaveAttribute("href", "/sizepass");
  });

  it("shows cancel button for active subscription", async () => {
    vi.mocked(getSubscriptionMock).mockResolvedValue({
      plan: "monthly",
      status: "active",
    });

    renderSettings("parent");

    expect(
      await screen.findByRole("button", { name: /cancel subscription/i }),
    ).toBeInTheDocument();
  });

  it("does not show upgrade prompt for SizePass users", async () => {
    vi.mocked(getSubscriptionMock).mockResolvedValue({
      plan: "sizepass",
      status: "active",
    });

    renderSettings();

    await screen.findByText("SizePass");
    expect(
      screen.queryByRole("button", { name: /upgrade/i }),
    ).not.toBeInTheDocument();
  });

  it("child sees request account deletion button", async () => {
    vi.mocked(getSubscriptionMock).mockResolvedValue({ plan: "free", status: "free" });

    renderSettings("child");

    expect(await screen.findByRole("button", { name: /request account deletion/i })).toBeInTheDocument();
  });

  it("child clicks request deletion → sees confirmation → confirms → sees success message", async () => {
    const user = userEvent.setup();
    vi.mocked(getSubscriptionMock).mockResolvedValue({ plan: "free", status: "free" });
    vi.mocked(requestAccountDeletionMock).mockResolvedValue({ id: 1, child_id: 1, status: "pending" });

    renderSettings("child");

    await user.click(await screen.findByRole("button", { name: /request account deletion/i }));

    expect(await screen.findByText(/this action cannot be undone/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /confirm/i }));

    expect(requestAccountDeletionMock).toHaveBeenCalled();
    expect(await screen.findByText(/deletion request has been sent/i)).toBeInTheDocument();
  });

  it("parent sees delete my account button", async () => {
    vi.mocked(getSubscriptionMock).mockResolvedValue({ plan: "free", status: "free" });

    renderSettings("parent");

    expect(await screen.findByRole("button", { name: /delete my account/i })).toBeInTheDocument();
  });

  it("parent clicks delete account → sees confirmation → confirms → logs out", async () => {
    const user = userEvent.setup();
    vi.mocked(getSubscriptionMock).mockResolvedValue({ plan: "free", status: "free" });
    vi.mocked(deleteOwnAccountMock).mockResolvedValue({ detail: "Deleted" });

    renderSettings("parent");

    await user.click(await screen.findByRole("button", { name: /delete my account/i }));

    expect(await screen.findByText(/this action cannot be undone/i)).toBeInTheDocument();
    expect(screen.getByText(/permanently deleted/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /confirm/i }));

    expect(deleteOwnAccountMock).toHaveBeenCalled();
  });

  it("parent does not see request deletion button (only children do)", async () => {
    vi.mocked(getSubscriptionMock).mockResolvedValue({ plan: "free", status: "free" });

    renderSettings("parent");

    await screen.findByRole("button", { name: /delete my account/i });
    expect(screen.queryByRole("button", { name: /request account deletion/i })).not.toBeInTheDocument();
  });

  it("child does not see delete my account button (only parents do)", async () => {
    vi.mocked(getSubscriptionMock).mockResolvedValue({ plan: "free", status: "free" });

    renderSettings("child");

    await screen.findByRole("button", { name: /request account deletion/i });
    expect(screen.queryByRole("button", { name: /delete my account/i })).not.toBeInTheDocument();
  });

  it("child can cancel deletion request confirmation", async () => {
    const user = userEvent.setup();
    vi.mocked(getSubscriptionMock).mockResolvedValue({ plan: "free", status: "free" });

    renderSettings("child");

    await user.click(await screen.findByRole("button", { name: /request account deletion/i }));
    expect(screen.getByText(/this action cannot be undone/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /cancel/i }));
    expect(screen.queryByText(/this action cannot be undone/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /request account deletion/i })).toBeInTheDocument();
  });

  it("E2E: child requests deletion → sees confirmation → confirms → sees success", async () => {
    const user = userEvent.setup();

    // Step 1: Child sees settings with deletion option
    vi.mocked(getSubscriptionMock).mockResolvedValue({ plan: "free", status: "free" });
    vi.mocked(requestAccountDeletionMock).mockResolvedValue({ id: 1, child_id: 1, status: "pending" });

    renderSettings("child");

    // Step 2: Click request deletion
    await user.click(await screen.findByRole("button", { name: /request account deletion/i }));

    // Step 3: See warning and confirm
    expect(screen.getByText(/this action cannot be undone/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /confirm/i }));

    // Step 4: See success message, button is gone
    expect(await screen.findByText(/deletion request has been sent/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /request account deletion/i })).not.toBeInTheDocument();
  });

  it("E2E: parent deletes own account → sees confirmation → confirms → logged out", async () => {
    const user = userEvent.setup();
    vi.mocked(getSubscriptionMock).mockResolvedValue({ plan: "free", status: "free" });
    vi.mocked(deleteOwnAccountMock).mockResolvedValue({ detail: "Deleted" });

    renderSettings("parent");

    await user.click(await screen.findByRole("button", { name: /delete my account/i }));
    expect(screen.getByText(/permanently deleted/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /confirm/i }));

    expect(deleteOwnAccountMock).toHaveBeenCalled();
  });

  it("child sees nickname edit form in settings", async () => {
    vi.mocked(getSubscriptionMock).mockResolvedValue({ plan: "free", status: "free" });
    vi.mocked(getProfileMock).mockResolvedValue({
      nickname: "OldNick",
      xp: 0, level: 1, level_name: "Beginner", progress_percent: 0,
      xp_for_next_level: 100, streak: 0, exbucks_balance: 0,
      badges: ["Freemium"], transactions: [],
    } as ProfileResponse);

    renderSettings("child");

    expect(await screen.findByLabelText(/nickname/i)).toBeInTheDocument();
    expect(screen.getByDisplayValue("OldNick")).toBeInTheDocument();
  });

  it("child submits nickname change from settings", async () => {
    const user = userEvent.setup();
    vi.mocked(getSubscriptionMock).mockResolvedValue({ plan: "free", status: "free" });
    vi.mocked(getProfileMock).mockResolvedValue({
      nickname: null,
      xp: 0, level: 1, level_name: "Beginner", progress_percent: 0,
      xp_for_next_level: 100, streak: 0, exbucks_balance: 0,
      badges: ["Freemium"], transactions: [],
    } as ProfileResponse);
    vi.mocked(setNicknameMock).mockResolvedValue({ nickname: "NewNick", nickname_changes: 1 });

    renderSettings("child");

    const input = await screen.findByLabelText(/nickname/i);
    await user.type(input, "NewNick");
    await user.click(screen.getByRole("button", { name: /save nickname/i }));

    expect(setNicknameMock).toHaveBeenCalledWith("NewNick");
  });

  it("parent does not see nickname form", async () => {
    vi.mocked(getSubscriptionMock).mockResolvedValue({ plan: "free", status: "free" });

    renderSettings("parent");

    await screen.findByText("Settings");
    expect(screen.queryByLabelText(/nickname/i)).not.toBeInTheDocument();
  });

  it("E2E: free user sees upgrade prompts → SizePass user sees premium features", async () => {
    // Step 1: Free user sees upgrade prompt on settings
    vi.mocked(getSubscriptionMock).mockResolvedValue({
      plan: "free",
      status: "free",
    });

    const { unmount: u1 } = renderSettings("parent");

    expect(await screen.findByText("Free")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /upgrade/i }),
    ).toBeInTheDocument();
    u1();

    // Step 2: SizePass user sees active status, no upgrade prompt
    vi.mocked(getSubscriptionMock).mockResolvedValue({
      plan: "sizepass",
      status: "active",
    });

    const { unmount: u2 } = renderSettings("parent");

    expect(await screen.findByText("SizePass")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /upgrade/i }),
    ).not.toBeInTheDocument();
    u2();
  });

  describe("responsive layout", () => {
    it("destructive buttons have minimum 44px touch target on mobile", async () => {
      vi.mocked(getSubscriptionMock).mockResolvedValue({ plan: "free", status: "free" });

      renderSettings("parent");

      const deleteBtn = await screen.findByRole("button", { name: /delete my account/i });
      expect(deleteBtn.className).toMatch(/min-h-\[44px\]/);
    });

    it("nickname form stacks vertically on mobile", async () => {
      vi.mocked(getSubscriptionMock).mockResolvedValue({ plan: "free", status: "free" });
      vi.mocked(getProfileMock).mockResolvedValue({
        nickname: "Nick",
        xp: 0, level: 1, level_name: "Beginner", progress_percent: 0,
        xp_for_next_level: 100, streak: 0, exbucks_balance: 0,
        badges: ["Freemium"], transactions: [],
      } as ProfileResponse);

      renderSettings("child");

      const nicknameInput = await screen.findByLabelText(/nickname/i);
      const form = nicknameInput.closest("form");
      expect(form).toBeInTheDocument();
      expect(form!.className).toMatch(/flex-col/);
      expect(form!.className).toMatch(/sm:flex-row/);
    });

    it("cancel subscription button has minimum 44px touch target on mobile", async () => {
      vi.mocked(getSubscriptionMock).mockResolvedValue({ plan: "monthly", status: "active" });

      renderSettings("parent");

      const cancelBtn = await screen.findByRole("button", { name: /cancel subscription/i });
      expect(cancelBtn.className).toMatch(/min-h-\[44px\]/);
    });
  });

  describe("push notifications", () => {
    it("renders the push card with an Enable button when supported and not subscribed", async () => {
      vi.mocked(getSubscriptionMock).mockResolvedValue({ plan: "free", status: "free" });

      renderSettings("parent");

      expect(await screen.findByText(/push notifications/i)).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /enable notifications/i }),
      ).toBeInTheDocument();
    });

    it("clicking Enable calls the hook's enable()", async () => {
      const user = userEvent.setup();
      vi.mocked(getSubscriptionMock).mockResolvedValue({ plan: "free", status: "free" });

      renderSettings("parent");

      await user.click(await screen.findByRole("button", { name: /enable notifications/i }));
      expect(pushState.enable).toHaveBeenCalled();
    });

    it("shows a Disable button when subscribed and calls disable() on click", async () => {
      const user = userEvent.setup();
      vi.mocked(getSubscriptionMock).mockResolvedValue({ plan: "free", status: "free" });
      pushState.isSubscribed = true;

      renderSettings("parent");

      await user.click(await screen.findByRole("button", { name: /disable notifications/i }));
      expect(pushState.disable).toHaveBeenCalled();
    });

    it("shows an unsupported message instead of a toggle when push is unavailable", async () => {
      vi.mocked(getSubscriptionMock).mockResolvedValue({ plan: "free", status: "free" });
      pushState.isSupported = false;

      renderSettings("parent");

      expect(await screen.findByText(/not supported on this device/i)).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /enable notifications/i }),
      ).not.toBeInTheDocument();
    });

    it("surfaces the push error message when enabling fails", async () => {
      vi.mocked(getSubscriptionMock).mockResolvedValue({ plan: "free", status: "free" });
      pushState.error = "Push not configured";

      renderSettings("parent");

      expect(await screen.findByText("Push not configured")).toBeInTheDocument();
    });
  });
});
