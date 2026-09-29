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
  if (typeof window === "undefined") {
    return;
  }
  window.fbq?.("track", "PageView");
  window.ttq?.page?.();
  window.gtag?.("event", "page_view");
}

export function trackAddToCart(product: Product): void {
  if (typeof window === "undefined") {
    return;
  }
  window.fbq?.("track", "AddToCart", {
    content_ids: [product.slug],
    content_name: product.name,
    value: product.price,
    currency: "USD",
  });
  window.ttq?.track("AddToCart", {
    content_id: product.slug,
    content_name: product.name,
    value: product.price,
    currency: "USD",
    quantity: 1,
  });
  window.gtag?.("event", "add_to_cart", {
    currency: "USD",
    value: product.price,
    items: [
      {
        item_id: product.slug,
        item_name: product.name,
        price: product.price,
        quantity: 1,
      },
    ],
  });
}

export function trackPlaceOrder(payload: { value: number; items: string[] }): void {
  if (typeof window === "undefined") {
    return;
  }
  const utm = getUtmParams();
  window.fbq?.("track", "Purchase", {
    value: payload.value,
    currency: "USD",
    content_ids: payload.items,
    ...utm,
  });
  window.ttq?.track("PlaceAnOrder", {
    value: payload.value,
    currency: "USD",
    content_ids: payload.items,
    ...utm,
  });
  window.gtag?.("event", "purchase", {
    value: payload.value,
    currency: "USD",
    items: payload.items,
    ...utm,
  });
}
