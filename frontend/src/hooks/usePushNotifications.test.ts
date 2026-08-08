import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { usePushNotifications } from "./usePushNotifications";

// Mocked API boundary (system boundary — allowed).
const subscribePush = vi.fn();
const unsubscribePush = vi.fn();
const getVapidPublicKey = vi.fn();

vi.mock("@/api", () => ({
  getVapidPublicKey: (...a: unknown[]) => getVapidPublicKey(...a),
  subscribePush: (...a: unknown[]) => subscribePush(...a),
  unsubscribePush: (...a: unknown[]) => unsubscribePush(...a),
}));

interface Setup {
  supported?: boolean;
  permission?: NotificationPermission;
  existingEndpoint?: string | null;
}

/**Install fake browser push APIs (Notification, serviceWorker, PushManager).*/
function setupBrowser({ supported = true, permission = "default", existingEndpoint = null }: Setup = {}) {
  (globalThis as unknown as { Notification: unknown }).Notification = {
    permission,
    async requestPermission() {
      return permission;
    },
  };
  if (supported) {
    (window as unknown as { PushManager: unknown }).PushManager = class {};
  } else {
    delete (window as unknown as { PushManager?: unknown }).PushManager;
  }

  const existingSub = existingEndpoint
    ? { endpoint: existingEndpoint, unsubscribe: vi.fn().mockResolvedValue(true) }
    : null;
  const pushManager = {
    subscribe: vi.fn().mockResolvedValue({
      endpoint: "https://push.example/send/new",
      keys: { p256dh: "p256dh-val", auth: "auth-val" },
    }),
    getSubscription: vi.fn().mockResolvedValue(existingSub),
  };
  const registration = { pushManager };
  Object.defineProperty(navigator, "serviceWorker", {
    value: { ready: Promise.resolve(registration) },
    configurable: true,
  });
  return { pushManager, registration, existingSub };
}

function restoreBrowser() {
  delete (globalThis as unknown as { Notification?: unknown }).Notification;
  delete (window as unknown as { PushManager?: unknown }).PushManager;
  Object.defineProperty(navigator, "serviceWorker", {
    value: undefined,
    configurable: true,
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  getVapidPublicKey.mockResolvedValue({ public_key: "BK_test_public_key" });
});

afterEach(() => {
  restoreBrowser();
});

describe("usePushNotifications", () => {
  it("F1: reports unsupported and enable() is a no-op when push is unavailable", async () => {
    setupBrowser({ supported: false });
    const { result } = renderHook(() => usePushNotifications());

    expect(result.current.isSupported).toBe(false);
    await act(async () => {
      await result.current.enable();
    });
    expect(subscribePush).not.toHaveBeenCalled();
    expect(getVapidPublicKey).not.toHaveBeenCalled();
    expect(result.current.isSubscribed).toBe(false);
  });

  it("F2: enable() requests permission, subscribes the browser, and POSTs the subscription", async () => {
    const { pushManager } = setupBrowser({ permission: "granted" });
    const { result } = renderHook(() => usePushNotifications());

    await act(async () => {
      await result.current.enable();
    });

    expect(getVapidPublicKey).toHaveBeenCalled();
    expect(pushManager.subscribe).toHaveBeenCalledWith(
      expect.objectContaining({
        userVisibleOnly: true,
        applicationServerKey: expect.any(Uint8Array),
      }),
    );
    expect(subscribePush).toHaveBeenCalledWith({
      endpoint: "https://push.example/send/new",
      keys: { p256dh: "p256dh-val", auth: "auth-val" },
    });
    expect(result.current.isSubscribed).toBe(true);
  });

  it("F3: enable() is a no-op when the user denies permission", async () => {
    setupBrowser({ permission: "denied" });
    const { result } = renderHook(() => usePushNotifications());

    await act(async () => {
      await result.current.enable();
    });

    expect(subscribePush).not.toHaveBeenCalled();
    expect(result.current.isSubscribed).toBe(false);
  });

  it("F4: disable() unsubscribes the browser and POSTs the unsubscribe", async () => {
    const { pushManager, existingSub } = setupBrowser({
      permission: "granted",
      existingEndpoint: "https://push.example/send/existing",
    });
    const { result } = renderHook(() => usePushNotifications());

    // First subscribe so isSubscribed flips on.
    await act(async () => {
      await result.current.enable();
    });
    // Reset getSubscription to return the existing sub for disable().
    pushManager.getSubscription.mockResolvedValue(existingSub);

    await act(async () => {
      await result.current.disable();
    });

    expect(existingSub?.unsubscribe).toHaveBeenCalled();
    expect(unsubscribePush).toHaveBeenCalledWith("https://push.example/send/existing");
    await waitFor(() => {
      expect(result.current.isSubscribed).toBe(false);
    });
  });

  it("F5: enable() surfaces an error when the VAPID key fetch fails instead of failing silently", async () => {
    setupBrowser({ permission: "granted" });
    getVapidPublicKey.mockRejectedValue(new Error("Push not configured"));
    const { result } = renderHook(() => usePushNotifications());

    await act(async () => {
      await result.current.enable();
    });

    expect(result.current.error).not.toBeNull();
    expect(result.current.isSubscribed).toBe(false);
    expect(subscribePush).not.toHaveBeenCalled();
  });

  it("F6: a successful enable() clears a previous error", async () => {
    setupBrowser({ permission: "granted" });
    const { result } = renderHook(() => usePushNotifications());

    // First attempt fails.
    getVapidPublicKey.mockRejectedValueOnce(new Error("Push not configured"));
    await act(async () => {
      await result.current.enable();
    });
    expect(result.current.error).not.toBeNull();

    // Second attempt succeeds.
    await act(async () => {
      await result.current.enable();
    });
    expect(result.current.error).toBeNull();
    expect(result.current.isSubscribed).toBe(true);
  });

  it("F7: reflects an existing browser subscription as On on mount (persists across Settings visits)", async () => {
    setupBrowser({
      permission: "granted",
      existingEndpoint: "https://push.example/send/existing",
    });
    const { result } = renderHook(() => usePushNotifications());

    await waitFor(() => {
      expect(result.current.isSubscribed).toBe(true);
    });
    expect(subscribePush).not.toHaveBeenCalled(); // bez ponownej rejestracji
  });
});
