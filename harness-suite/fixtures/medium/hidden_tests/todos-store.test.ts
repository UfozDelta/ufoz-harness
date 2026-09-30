// @vitest-environment node
import { beforeEach, describe, expect, it } from "vitest";

import { addTodo, getTodo, listTodos, removeTodo, resetTodos, toggleTodo } from "./lib/todos-store";

describe("todos store", () => {
  beforeEach(() => {
    resetTodos();
  });

  it("starts empty after a reset", () => {
    resetTodos();
    expect(listTodos()).toEqual([]);
  });

  it("adds todos with increasing ids, not done, and stores the title as given", () => {
    const first = addTodo("write docs");
    const second = addTodo("ship it");
    expect([first.id, second.id]).toEqual([1, 2]);
    expect(first.title).toBe("write docs");
    expect(first.done).toBe(false);
  });

  it("starts ids from 1 again after a reset", () => {
    addTodo("one");
    resetTodos();
    expect(addTodo("two").id).toBe(1);
  });

  it("hands out copies, so callers cannot mutate the store", () => {
    addTodo("original");
    const listed = listTodos();
    listed[0].title = "mutated";
    expect(listTodos()[0].title).toBe("original");
  });

  it("gets one todo by id and returns null for a miss", () => {
    addTodo("findable");
    expect(getTodo(1)?.title).toBe("findable");
    expect(getTodo(99)).toBeNull();
  });

  it("toggles done and returns null for a miss", () => {
    addTodo("toggle me");
    expect(toggleTodo(1)?.done).toBe(true);
    expect(toggleTodo(1)?.done).toBe(false);
    expect(toggleTodo(99)).toBeNull();
  });

  it("removes a todo and reports whether it existed", () => {
    addTodo("delete me");
    expect(removeTodo(1)).toBe(true);
    expect(removeTodo(1)).toBe(false);
    expect(listTodos()).toEqual([]);
  });
});
