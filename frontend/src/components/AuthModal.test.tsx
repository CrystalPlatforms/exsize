import { render, screen, waitFor, act, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api")>();
  return {
    ...actual,
    login: vi.fn(),
    adminLogin: vi.fn(),
    register: vi.fn(),
    getMe: vi.fn(),
    setToken: vi.fn(),
    getToken: vi.fn(() => null),
    googleLoginStatus: vi.fn(() => Promise.resolve({ enabled: false })),
  };
});

import App from "@/App";
import {
  login as loginMock,
  adminLogin as adminLoginMock,
  register as registerMock,
  getMe as getMeMock,
  googleLoginStatus as googleStatusMock,
} from "@/api";

function renderApp(route = "/") {
  window.history.pushState({}, "", route);
  return render(<App />);
}

describe("AuthModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it("shows auth modal with login form when user is not authenticated", () => {
    renderApp();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it("has Login and Register tabs, defaults to Login", () => {
    renderApp();
    expect(screen.getByRole("tab", { name: /login/i })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: /register/i })).toHaveAttribute("aria-selected", "false");
  });

  it("switches to register form when Register tab is clicked", async () => {
    const user = userEvent.setup();
    renderApp();

    await user.click(screen.getByRole("tab", { name: /register/i }));

    expect(screen.getByRole("tab", { name: /register/i })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByLabelText(/role/i)).toBeInTheDocument();
  });

  it("remains open after clicking the overlay backdrop", async () => {
    const user = userEvent.setup();
    renderApp();
    const overlay = document.querySelector("[data-slot='dialog-overlay']")!;
    await user.click(overlay);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("does not render a close button", () => {
    renderApp();
    expect(screen.queryByRole("button", { name: /close/i })).not.toBeInTheDocument();
  });

  it("switches back to login form when Login tab is clicked", async () => {
    const user = userEvent.setup();
    renderApp();

    await user.click(screen.getByRole("tab", { name: /register/i }));
    await user.click(screen.getByRole("tab", { name: /login/i }));

    expect(screen.getByRole("tab", { name: /login/i })).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByLabelText(/role/i)).not.toBeInTheDocument();
  });

  it("closes modal and shows app after successful login", async () => {
    const user = userEvent.setup();
    vi.mocked(loginMock).mockResolvedValue({
      access_token: "test-token",
      token_type: "bearer",
    });
    vi.mocked(getMeMock).mockResolvedValue({
      id: 1,
      email: "parent@test.com",
      role: "parent",
      language: "en",
    });

    renderApp();
    await user.type(screen.getByLabelText(/email/i), "parent@test.com");
    await user.type(screen.getByLabelText(/password/i), "password123");
    await user.click(screen.getByRole("button", { name: /^login$/i }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("closes modal and shows app after successful registration", async () => {
    const user = userEvent.setup();
    vi.mocked(registerMock).mockResolvedValue(undefined as never);
    vi.mocked(loginMock).mockResolvedValue({
      access_token: "new-token",
      token_type: "bearer",
    });
    vi.mocked(getMeMock).mockResolvedValue({
      id: 2,
      email: "new@test.com",
      role: "parent",
      language: "en",
    });

    renderApp();
    await user.click(screen.getByRole("tab", { name: /register/i }));
    await user.type(screen.getByLabelText(/email/i), "new@test.com");
    await user.type(screen.getByLabelText(/password/i), "password123");
    await user.click(screen.getByRole("button", { name: /^register$/i }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    expect(registerMock).toHaveBeenCalledWith("new@test.com", "password123", "parent");
  });

  it("shows admin secret field when Login as Admin is checked", async () => {
    const user = userEvent.setup();
    renderApp();

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/admin secret/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: /login as admin/i }));

    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/admin secret/i)).toBeInTheDocument();
  });

  it("calls adminLogin API when logging in as admin", async () => {
    const user = userEvent.setup();
    vi.mocked(adminLoginMock).mockResolvedValue({
      access_token: "admin-token",
      token_type: "bearer",
    });
    vi.mocked(getMeMock).mockResolvedValue({
      id: 1,
      email: "admin@test.com",
      role: "admin",
      language: "en",
    });

    renderApp();
    await user.click(screen.getByRole("checkbox", { name: /login as admin/i }));
    await user.type(screen.getByLabelText(/admin secret/i), "my-secret");
    await user.click(screen.getByRole("button", { name: /^login$/i }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    expect(adminLoginMock).toHaveBeenCalledWith("my-secret");
    expect(loginMock).not.toHaveBeenCalled();
  });

  it("shows slow-loading message in login form after 3 seconds", async () => {
    const user = userEvent.setup();

    vi.mocked(loginMock).mockImplementation(
      () => new Promise(() => {}), // never resolves
    );

    renderApp();
    await user.type(screen.getByLabelText(/email/i), "test@test.com");
    await user.type(screen.getByLabelText(/password/i), "password");

    vi.useFakeTimers();
    fireEvent.submit(screen.getByRole("button", { name: /^login$/i }).closest("form")!);

    expect(screen.queryByText(/serwer się budzi/i)).not.toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(3000);
    });

    expect(screen.getByText(/serwer się budzi/i)).toBeInTheDocument();
    vi.useRealTimers();
  });

  it("shows slow-loading message in register form after 3 seconds", async () => {
    const user = userEvent.setup();

    vi.mocked(registerMock).mockImplementation(
      () => new Promise(() => {}),
    );

    renderApp();
    await user.click(screen.getByRole("tab", { name: /register/i }));
    await user.type(screen.getByLabelText(/email/i), "test@test.com");
    await user.type(screen.getByLabelText(/password/i), "password");

    vi.useFakeTimers();
    fireEvent.submit(screen.getByRole("button", { name: /^register$/i }).closest("form")!);

    expect(screen.queryByText(/serwer się budzi/i)).not.toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(3000);
    });

    expect(screen.getByText(/serwer się budzi/i)).toBeInTheDocument();
    vi.useRealTimers();
  });

  it("browser back button does not bypass the modal", () => {
    window.history.pushState({}, "", "/dashboard");
    renderApp();
    window.history.back();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("always shows Continue with Google when the backend enables it", async () => {
    vi.mocked(googleStatusMock).mockResolvedValue({ enabled: true });
    renderApp();
    expect(await screen.findByRole("button", { name: /continue with google/i })).toBeInTheDocument();
  });

  it("keeps Continue with Google visible without keys and explains on click", async () => {
    const user = userEvent.setup();
    vi.mocked(googleStatusMock).mockResolvedValue({ enabled: false });
    renderApp();
    const button = screen.getByRole("button", { name: /continue with google/i });
    await user.click(button);
    expect(
      screen.getByText(/google login is not configured on the server/i),
    ).toBeInTheDocument();
    expect(window.location.href).not.toContain("/api/auth/google/authorize");
  });
});
