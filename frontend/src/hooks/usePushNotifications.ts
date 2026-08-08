import { useCallback, useState } from "react";
import { getVapidPublicKey, subscribePush, unsubscribePush } from "@/api";

/**Convert a base64url VAPID public key into the Uint8Array the Push API expects.*/
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  return Uint8Array.from(rawData, (char) => char.charCodeAt(0));
}

function pushSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

export function usePushNotifications() {
  const [isSupported] = useState(() => pushSupported());
  const [permission, setPermission] = useState<NotificationPermission>(() =>
    typeof window !== "undefined" && "Notification" in window
      ? Notification.permission
      : "default",
  );
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const enable = useCallback(async () => {
    if (!pushSupported()) return;
    setError(null);
    try {
      const { public_key } = await getVapidPublicKey();
      const result = await Notification.requestPermission();
      setPermission(result);
      if (result !== "granted") {
        if (result === "denied") setError("Notifications are blocked in your browser settings.");
        return;
      }
      const registration = await navigator.serviceWorker.ready;
      const sub = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(public_key),
      });
      // PushSubscription serializes to { endpoint, keys: { p256dh, auth } }.
      const json = JSON.parse(JSON.stringify(sub)) as {
        endpoint: string;
        keys: { p256dh: string; auth: string };
      };
      await subscribePush({ endpoint: json.endpoint, keys: json.keys });
      setIsSubscribed(true);
    } catch (err) {
      // Graceful but visible: never break the app, but surface the failure so
      // the user (and dev) knows push didn't activate.
      setError(err instanceof Error ? err.message : "Could not enable notifications.");
    }
  }, []);

  const disable = useCallback(async () => {
    if (!pushSupported()) return;
    setError(null);
    try {
      const registration = await navigator.serviceWorker.ready;
      const sub = await registration.pushManager.getSubscription();
      if (sub) {
        const endpoint = sub.endpoint;
        await sub.unsubscribe();
        await unsubscribePush(endpoint);
      }
      setIsSubscribed(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not disable notifications.");
    }
  }, []);

  return { isSupported, permission, isSubscribed, error, enable, disable };
}
