// @vitest-environment node
import { describe, expect, it } from "vitest";

import { MAX_TITLE_LENGTH, isValidTitle, validateDone, validateTitle } from "./lib/validate";

describe("validateTitle", () => {
  it("returns the trimmed title when it is usable", () => {
    expect(validateTitle("  plan the suite  ")).toBe("plan the suite");
  });

  it("rejects non-strings, blanks and over-long titles", () => {
    expect(validateTitle(undefined)).toBeNull();
    expect(validateTitle(7)).toBeNull();
    expect(validateTitle(null)).toBeNull();
    expect(validateTitle("   ")).toBeNull();
    expect(validateTitle("x".repeat(MAX_TITLE_LENGTH + 1))).toBeNull();
  });

  it("accepts a title of exactly the maximum length", () => {
    expect(validateTitle("x".repeat(MAX_TITLE_LENGTH))).toHaveLength(MAX_TITLE_LENGTH);
  });
});

describe("isValidTitle", () => {
  it("mirrors validateTitle", () => {
    expect(isValidTitle("ok")).toBe(true);
    expect(isValidTitle(" ")).toBe(false);
  });
});

describe("validateDone", () => {
  it("accepts booleans and defaults anything else to false", () => {
    expect(validateDone(true)).toBe(true);
    expect(validateDone(false)).toBe(false);
    expect(validateDone("yes")).toBe(false);
    expect(validateDone(undefined)).toBe(false);
  });
});
