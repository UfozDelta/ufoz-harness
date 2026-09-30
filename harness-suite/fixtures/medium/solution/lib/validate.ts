export const MAX_TITLE_LENGTH = 120;

export function validateTitle(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const title = raw.trim();
  if (title.length === 0) return null;
  if (title.length > MAX_TITLE_LENGTH) return null;
  return title;
}

export function isValidTitle(raw: unknown): boolean {
  return validateTitle(raw) !== null;
}

export function validateDone(raw: unknown): boolean {
  return typeof raw === "boolean" ? raw : false;
}
