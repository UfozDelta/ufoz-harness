export type UtmParams = Record<string, string>;

export const UTM_STORAGE_KEY = "utm_params";

const UTM_KEYS = ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"] as const;

export function captureUtmParams(): UtmParams {
  if (typeof window === "undefined") {
    return {};
  }
  try {
    const stored = sessionStorage.getItem(UTM_STORAGE_KEY);
    if (stored) {
      try {
        return JSON.parse(stored) as UtmParams;
      } catch {
        return {};
      }
    }
    const params = new URLSearchParams(window.location.search);
    const found: UtmParams = {};
    for (const key of UTM_KEYS) {
      const value = params.get(key);
      if (value) {
        found[key] = value;
      }
    }
    if (Object.keys(found).length > 0) {
      sessionStorage.setItem(UTM_STORAGE_KEY, JSON.stringify(found));
      return found;
    }
    return {};
  } catch {
    return {};
  }
}

export function getUtmParams(): UtmParams {
  if (typeof window === "undefined") {
    return {};
  }
  try {
    const stored = sessionStorage.getItem(UTM_STORAGE_KEY);
    if (!stored) {
      return {};
    }
    return JSON.parse(stored) as UtmParams;
  } catch {
    return {};
  }
}
