// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import HomePage from "./app/page";
import type { Item } from "./lib/api-client";

let fetchMock: ReturnType<typeof vi.fn>;

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("items page", () => {
  it("renders the count from the pluraliser", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));
    render(await HomePage());
    expect(screen.getByTestId("item-count").textContent).toBe("0 items");
  });

  it("uses the singular form for exactly one item", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse([{ id: 1, name: "Widget", sku: "W-1", price: 1, quantity: 1 }]),
    );
    render(await HomePage());
    expect(screen.getByTestId("item-count").textContent).toBe("1 item");
  });

  it("delegates rendering to ItemList", async () => {
    const items: Item[] = [
      { id: 1, name: "Widget", sku: "W-1", price: 9.5, quantity: 4 },
      { id: 2, name: "Gadget", sku: "G-2", price: 3, quantity: 1 },
    ];
    fetchMock.mockResolvedValue(jsonResponse(items));
    render(await HomePage());
    const rows = screen.getAllByTestId("item-row");
    expect(rows.map((row) => row.getAttribute("data-sku"))).toEqual(["W-1", "G-2"]);
  });

  it("shows the empty label when the API returns nothing", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));
    render(await HomePage());
    expect(screen.getByTestId("item-empty")).not.toBeNull();
  });

  it("asks the api client for the item list", async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));
    await HomePage();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]![0]).toBe("/api/items");
  });
});
