import { describe, it, expect } from "vitest";
import { pluralItems } from "./format";

describe("pluralItems", () => {
  it("pluralizes zero", () => {
    expect(pluralItems(0)).toBe("0 items");
  });

  it("uses the singular for one", () => {
    expect(pluralItems(1)).toBe("1 item");
  });

  it("pluralizes larger counts", () => {
    expect(pluralItems(5)).toBe("5 items");
  });
});
