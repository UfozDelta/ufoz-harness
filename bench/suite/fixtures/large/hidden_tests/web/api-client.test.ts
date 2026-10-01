import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiClient, ApiError, createApiClient } from "./lib/api-client";

const item = { id: 1, name: "Widget", sku: "W-1", price: 9.5, quantity: 4 };

let fetchMock: ReturnType<typeof vi.fn>;

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("createApiClient", () => {
  it("defaults to the /api base url", () => {
    expect(createApiClient().baseUrl).toBe("/api");
  });

  it("accepts an explicit base url", () => {
    expect(createApiClient("http://localhost:8000/api").baseUrl).toBe(
      "http://localhost:8000/api",
    );
  });

  it("drops a trailing slash from the base url", () => {
    expect(new ApiClient("http://localhost:8000/api/").baseUrl).toBe(
      "http://localhost:8000/api",
    );
  });
});

describe("listItems", () => {
  it("requests /items and returns the parsed body", async () => {
    fetchMock.mockResolvedValue(jsonResponse([item]));
    await expect(new ApiClient().listItems()).resolves.toEqual([item]);
    expect(fetchMock).toHaveBeenCalledWith("/api/items", undefined);
  });
});

describe("getItem", () => {
  it("requests the item by id", async () => {
    fetchMock.mockResolvedValue(jsonResponse(item));
    await new ApiClient("http://api.test").getItem(7);
    expect(fetchMock.mock.calls[0]![0]).toBe("http://api.test/items/7");
  });
});

describe("createItem", () => {
  it("posts JSON and returns the created item", async () => {
    fetchMock.mockResolvedValue(jsonResponse(item, 201));
    const created = await new ApiClient().createItem({
      name: "Widget",
      sku: "W-1",
      price: 9.5,
    });
    expect(created).toEqual(item);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("/api/items");
    expect(init.method).toBe("POST");
    expect(init.headers["content-type"]).toBe("application/json");
    expect(JSON.parse(init.body as string)).toEqual({
      name: "Widget",
      sku: "W-1",
      price: 9.5,
    });
  });
});

describe("deleteItem", () => {
  it("sends DELETE and resolves to undefined on 204", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    await expect(new ApiClient().deleteItem(3)).resolves.toBeUndefined();
    expect(fetchMock.mock.calls[0]).toEqual(["/api/items/3", { method: "DELETE" }]);
  });
});

describe("stats", () => {
  it("requests /stats and returns the payload", async () => {
    const stats = { total: 1, total_quantity: 4, total_value: 38.0, avg_price: 38.0 };
    fetchMock.mockResolvedValue(jsonResponse(stats));
    await expect(new ApiClient().stats()).resolves.toEqual(stats);
    expect(fetchMock.mock.calls[0]![0]).toBe("/api/stats");
  });
});

describe("search", () => {
  it("url-encodes the query", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ query: "a b", count: 0, items: [] }));
    await new ApiClient().search("a b");
    expect(fetchMock.mock.calls[0]![0]).toBe("/api/search?q=a%20b");
  });
});

describe("error handling", () => {
  it("throws an ApiError carrying the status", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "Item not found" }, 404));
    await expect(new ApiClient().getItem(99)).rejects.toBeInstanceOf(ApiError);
  });

  it("exposes the failing status on the error", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "sku already exists" }, 409));
    await new ApiClient()
      .createItem({ name: "n", sku: "s", price: 1 })
      .catch((error: unknown) => {
        expect(error).toBeInstanceOf(ApiError);
        expect((error as ApiError).status).toBe(409);
        expect((error as ApiError).message).toContain("409");
      });
  });
});
