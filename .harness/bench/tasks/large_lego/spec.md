# Spec

## Goal
Build a fresh frontend-only storefront for a Lego dropshipping store in `storefront/`:
catalog page, product detail page (PDP), client-side cart, checkout stub, and Meta Pixel /
TikTok Pixel / Google gtag wiring with PageView plus AddToCart and PlaceOrder events,
with UTM params captured on first load and attached to the order event.

## Starting point
Nothing exists. `storefront/` is created from scratch. No seed. No backend, no payment
processor, no database.

## Assumptions / Decisions (fixed — the executor must not re-decide)
- App root is `storefront/` (Next.js App Router inside it). Everything lives under that dir.
  Node 18+ and network access for `npm install` are assumed present.
- Pinned deps: `next@14.2.15`, `react@18.3.1`, `react-dom@18.3.1`; dev: `typescript@5.4.5`,
  `@types/node@20.14.10`, `@types/react@18.3.3`, `@types/react-dom@18.3.0`. No other packages ever
  (no tailwind, no state library, no analytics SDK, no UI kit).
- Product data is hardcoded: `storefront/lib/products.ts` exports
  `export type Product = { slug: string; name: string; price: number; image: string; description: string }`
  and `export const products: Product[]` with exactly 6 Lego sets. `price` is USD as a number.
  Every `image` is `"/images/placeholder.svg"` (one file, `storefront/public/images/placeholder.svg`).
  Images render with plain `<img>`; `next/image` is not used.
- Cart is client-only: `storefront/lib/cart-context.tsx` — `CartProvider`, `useCart()`,
  `addItem(product)`, `removeItem(slug)`, `clearCart()`, persisted in `localStorage` key `lego_cart`.
- Analytics: `storefront/lib/analytics.ts` exports `trackPageView()`, `trackAddToCart(product)`,
  `trackPlaceOrder(payload)`; each calls `window.fbq`, `window.ttq` and `window.gtag` defensively
  (no-op when undefined). `storefront/components/AnalyticsScripts.tsx` is a `"use client"` component
  rendering the three `next/script` snippets and, in `useEffect`, calling `captureUtmParams()` then
  `trackPageView()`.
- Env vars (placeholders committed in `storefront/.env.local`):
  `NEXT_PUBLIC_META_PIXEL_ID=000000000000000`,
  `NEXT_PUBLIC_TIKTOK_PIXEL_ID=CXXXXXXXXXXXXXXXXXXX`,
  `NEXT_PUBLIC_GA_MEASUREMENT_ID=G-XXXXXXXXXX`. Read with `process.env.NEXT_PUBLIC_*` only.
- UTM: `storefront/lib/utm.ts` — `captureUtmParams()` reads `utm_source, utm_medium, utm_campaign,
  utm_content, utm_term` from `location.search` and writes them to `sessionStorage` key `utm_params`
  ONLY if that key is not already set (first load wins); `getUtmParams()` reads it back.
  `trackPlaceOrder` attaches `getUtmParams()` to its event payload.
- Routes: `/` catalog, `/product/[slug]` PDP (unknown slug -> `notFound()`), `/cart`, `/checkout`.
  Checkout is a stub: shipping fields + "Place Order" button -> fires `trackPlaceOrder`, clears the
  cart, shows a confirmation. No fetch, no payment, no order id from a server.
- Styling: one plain `storefront/app/globals.css`. No CSS framework.
- `npm run build` inside `storefront/` must succeed, so `storefront/.next/` exists when you finish.
