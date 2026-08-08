import type { VitePWAOptions } from "vite-plugin-pwa"

export const pwaConfig: Partial<VitePWAOptions> = {
  registerType: "autoUpdate",
  // Service workers (required for push) are off by default in `vite dev`.
  // Enable them locally so push notifications can be exercised in dev.
  devOptions: { enabled: true },
  workbox: {
    globPatterns: ["**/*.{html,js,css,ico,png,svg,woff2}"],
    // Wczytuje nasze handlery push/notificationclick do wygenerowanego SW,
    // bez przełączania generateSW -> injectManifest (cachowanie zostaje).
    importScripts: ["/sw-push.js"],
    navigateFallback: "/offline.html",
    navigateFallbackDenylist: [/^\/api\//],
    runtimeCaching: [
      {
        urlPattern: /\.(?:js|css)$/,
        handler: "CacheFirst",
        options: {
          cacheName: "static-assets",
          expiration: { maxEntries: 50, maxAgeSeconds: 30 * 24 * 60 * 60 },
        },
      },
      {
        urlPattern: /\.(?:woff2?|ttf|eot)$/,
        handler: "CacheFirst",
        options: {
          cacheName: "fonts",
          expiration: { maxEntries: 20, maxAgeSeconds: 365 * 24 * 60 * 60 },
        },
      },
      {
        urlPattern: /\.(?:png|jpg|jpeg|gif|svg|ico|webp)$/,
        handler: "CacheFirst",
        options: {
          cacheName: "images",
          expiration: { maxEntries: 100, maxAgeSeconds: 30 * 24 * 60 * 60 },
        },
      },
    ],
  },
  manifest: {
    name: "ExSize",
    short_name: "ExSize",
    theme_color: "#1a7a5c",
    background_color: "#0a0a0a",
    display: "standalone",
    icons: [
      { src: "pwa-192x192.png", sizes: "192x192", type: "image/png" },
      { src: "pwa-512x512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "pwa-512x512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  },
}
