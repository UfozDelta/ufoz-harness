import { describe, it, expect } from "vitest";
import { formatCount } from "./format";

describe("formatCount", () => {
  it("pluralizes zero", () => {
    expect(formatCount(0)).toBe("0 todos");
  });

  it("uses the singular for one", () => {
    expect(formatCount(1)).toBe("1 todo");
  });

  it("pluralizes larger counts", () => {
    expect(formatCount(5)).toBe("5 todos");
  });
});
