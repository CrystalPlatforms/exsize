import { describe, it, expect } from "vitest"
import { pwaConfig } from "./pwa-config"

const manifest =
  typeof pwaConfig.manifest === "object" ? pwaConfig.manifest : undefined

describe("PWA config", () => {
  it("has app name ExSize", () => {
    expect(manifest?.name).toBe("ExSize")
    expect(manifest?.short_name).toBe("ExSize")
  })

  it("has theme and background colors", () => {
    expect(manifest?.theme_color).toBe("#1a7a5c")
    expect(manifest?.background_color).toBe("#0a0a0a")
  })

  it("uses standalone display mode", () => {
    expect(manifest?.display).toBe("standalone")
  })

  it("has icons at 192x192 and 512x512", () => {
    const icons = manifest?.icons
    expect(icons).toBeDefined()
    expect(icons).toContainEqual(
      expect.objectContaining({ sizes: "192x192", type: "image/png" })
    )
    expect(icons).toContainEqual(
      expect.objectContaining({ sizes: "512x512", type: "image/png" })
    )
  })

  it("registers service worker with autoUpdate for non-blocking registration", () => {
    expect(pwaConfig.registerType).toBe("autoUpdate")
  })

  it("enables the service worker in dev so push can be tested locally", () => {
    expect(pwaConfig.devOptions?.enabled).toBe(true)
  })

  it("precaches app shell files via workbox globPatterns", () => {
    const patterns = pwaConfig.workbox?.globPatterns
    expect(patterns).toBeDefined()
    expect(patterns).toContainEqual(expect.stringContaining("html"))
    expect(patterns).toContainEqual(expect.stringContaining("js"))
    expect(patterns).toContainEqual(expect.stringContaining("css"))
  })

  it("uses CacheFirst runtime caching for static assets", () => {
    const caching = pwaConfig.workbox?.runtimeCaching
    expect(caching).toBeDefined()
    expect(caching!.length).toBeGreaterThanOrEqual(1)

    const staticAssetRule = caching!.find((rule) =>
      rule.urlPattern instanceof RegExp
        ? rule.urlPattern.test("/assets/foo.js")
        : false
    )
    expect(staticAssetRule).toBeDefined()
    expect(staticAssetRule!.handler).toBe("CacheFirst")
  })

  it("caches font files with CacheFirst", () => {
    const caching = pwaConfig.workbox?.runtimeCaching
    const fontRule = caching!.find((rule) =>
      rule.urlPattern instanceof RegExp
        ? rule.urlPattern.test("/assets/font.woff2")
        : false
    )
    expect(fontRule).toBeDefined()
    expect(fontRule!.handler).toBe("CacheFirst")
  })

  it("caches image files with CacheFirst", () => {
    const caching = pwaConfig.workbox?.runtimeCaching
    const imageRule = caching!.find((rule) =>
      rule.urlPattern instanceof RegExp
        ? rule.urlPattern.test("/logo.png")
        : false
    )
    expect(imageRule).toBeDefined()
    expect(imageRule!.handler).toBe("CacheFirst")
  })

  it("serves offline.html as navigation fallback", () => {
    expect(pwaConfig.workbox?.navigateFallback).toBe("/offline.html")
  })

  it("excludes /api routes from navigation fallback", () => {
    const denylist = pwaConfig.workbox?.navigateFallbackDenylist
    expect(denylist).toBeDefined()
    expect(denylist!.some((re) => re.test("/api/health"))).toBe(true)
  })
})
