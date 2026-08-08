import { describe, it, expect, beforeAll } from "vitest"
import fs from "fs"
import path from "path"

describe("sw-push.js (service worker push handlers)", () => {
  let src: string

  beforeAll(() => {
    src = fs.readFileSync(
      path.resolve(__dirname, "../public/sw-push.js"),
      "utf-8"
    )
  })

  it("listens for the push event", () => {
    expect(src).toContain('addEventListener("push"')
  })

  it("shows a notification on push using the payload title/body", () => {
    expect(src).toContain("registration.showNotification")
    expect(src).toContain("payload.title")
    expect(src).toContain("payload.body")
  })

  it("falls back to payload.titles when body is absent (digest)", () => {
    expect(src).toContain("payload.titles")
  })

  it("listens for notificationclick and focuses an open window", () => {
    expect(src).toContain('addEventListener("notificationclick"')
    expect(src).toContain("clients.matchAll")
    expect(src).toContain(".focus()")
  })

  it("uses the app icon for the notification", () => {
    expect(src).toContain("/pwa-192x192.png")
  })
})
