import type { Product } from "./products";
import { getUtmParams } from "./utm";

declare global {
  interface Window {
    fbq?: (...args: any[]) => void;
    ttq?: { track: (...args: any[]) => void; page: () => void };
    gtag?: (...args: any[]) => void;
  }
}

export function trackPageView(): void {
  if (typeof window === "undefined") return;
  window.fbq?.("track", "PageView");
  window.ttq?.page?.();
  window.gtag?.("event", "page_view");
}

export function trackAddToCart(product: Product): void {
  if (typeof window === "undefined") return;
  const payload = {
    content_ids: [product.slug],
    content_name: product.name,
    value: product.price,
    currency: "USD",
  };
  window.fbq?.("track", "AddToCart", payload);
  window.ttq?.track("AddToCart", payload);
  window.gtag?.("event", "add_to_cart", payload);
}

export function trackPlaceOrder(payload: { value: number; items: string[] }): void {
  if (typeof window === "undefined") return;
  const enriched = { ...payload, currency: "USD", ...getUtmParams() };
  window.fbq?.("track", "Purchase", enriched);
  window.ttq?.track("PlaceAnOrder", enriched);
  window.gtag?.("event", "purchase", enriched);
}
