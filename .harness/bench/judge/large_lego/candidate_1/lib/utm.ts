export type UtmParams = Record<string, string>;

export const UTM_STORAGE_KEY = "utm_params";

const UTM_KEYS = ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"];

export function captureUtmParams(): UtmParams {
  if (typeof window === "undefined") return {};

  try {
    const existing = window.sessionStorage.getItem(UTM_STORAGE_KEY);
    if (existing) {
      return JSON.parse(existing) as UtmParams;
    }
  } catch {
    return {};
  }

  const params = new URLSearchParams(window.location.search);
  const found: UtmParams = {};
  for (const key of UTM_KEYS) {
    const value = params.get(key);
    if (value) found[key] = value;
  }

  if (Object.keys(found).length > 0) {
    try {
      window.sessionStorage.setItem(UTM_STORAGE_KEY, JSON.stringify(found));
    } catch {
      // ignore storage errors
    }
  }

  return found;
}

export function getUtmParams(): UtmParams {
  if (typeof window === "undefined") return {};

  try {
    const stored = window.sessionStorage.getItem(UTM_STORAGE_KEY);
    return stored ? (JSON.parse(stored) as UtmParams) : {};
  } catch {
    return {};
  }
}
