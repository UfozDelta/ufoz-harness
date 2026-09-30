// @vitest-environment node
import { beforeEach, describe, expect, it } from "vitest";

import { GET, POST } from "./app/api/todos/route";
import { resetTodos } from "./lib/todos-store";

function post(body: string): Request {
  return new Request("http://localhost/api/todos", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body,
  });
}

describe("GET /api/todos", () => {
  beforeEach(() => {
    resetTodos();
  });

  it("returns an empty array on a clean store", async () => {
    const res = await GET();
    expect(res.status).toBe(200);
    await expect(res.json()).resolves.toEqual([]);
  });

  it("returns the todos the store holds", async () => {
    await (await POST(post(JSON.stringify({ title: "write the fixture" })))).json();
    const res = await GET();
    const body = (await res.json()) as { title: string; done: boolean }[];
    expect(body).toHaveLength(1);
    expect(body[0].title).toBe("write the fixture");
    expect(body[0].done).toBe(false);
  });
});

describe("POST /api/todos", () => {
  beforeEach(() => {
    resetTodos();
  });

  it("creates a todo and answers 201", async () => {
    const res = await POST(post(JSON.stringify({ title: "  buy milk  " })));
    expect(res.status).toBe(201);
    const body = (await res.json()) as { id: number; title: string; done: boolean };
    expect(body.id).toBe(1);
    expect(body.title).toBe("buy milk");
    expect(body.done).toBe(false);
  });

  it("numbers todos from 1 and keeps creation order", async () => {
    await (await POST(post(JSON.stringify({ title: "first" })))).json();
    const second = await POST(post(JSON.stringify({ title: "second" })));
    expect(((await second.json()) as { id: number }).id).toBe(2);
    const list = (await (await GET()).json()) as { title: string }[];
    expect(list.map((t) => t.title)).toEqual(["first", "second"]);
  });

  it("rejects a missing title with 400", async () => {
    const res = await POST(post(JSON.stringify({})));
    expect(res.status).toBe(400);
    await expect(res.json()).resolves.toHaveProperty("error");
  });

  it("rejects a blank title with 400", async () => {
    const res = await POST(post(JSON.stringify({ title: "   " })));
    expect(res.status).toBe(400);
  });

  it("rejects a non-string title with 400", async () => {
    const res = await POST(post(JSON.stringify({ title: 42 })));
    expect(res.status).toBe(400);
  });

  it("rejects a broken JSON body with 400", async () => {
    const res = await POST(post("{not json"));
    expect(res.status).toBe(400);
  });
});
