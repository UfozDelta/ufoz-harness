import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import TodoList from "./components/TodoList";
import type { Todo } from "./lib/todos-store";

const todos: Todo[] = [
  { id: 1, title: "write the route", done: false },
  { id: 2, title: "write the store", done: true },
];

afterEach(cleanup);

describe("TodoList", () => {
  it("shows the empty label when there is nothing to do", () => {
    render(<TodoList todos={[]} emptyLabel="Nothing here yet" />);
    expect(screen.getByTestId("todo-empty").textContent).toBe("Nothing here yet");
  });

  it("renders one row per todo, in order", () => {
    render(<TodoList todos={todos} />);
    const rows = screen.getAllByRole("listitem");
    expect(rows.map((row) => row.textContent)).toEqual(["write the route", "write the store"]);
  });

  it("reflects the done state on the checkbox", () => {
    render(<TodoList todos={todos} />);
    const boxes = screen.getAllByRole("checkbox") as HTMLInputElement[];
    expect(boxes[0].checked).toBe(false);
    expect(boxes[1].checked).toBe(true);
  });

  it("calls onToggle with the todo id", () => {
    const onToggle = vi.fn();
    render(<TodoList todos={todos} onToggle={onToggle} />);
    fireEvent.click(screen.getAllByRole("checkbox")[1]);
    expect(onToggle).toHaveBeenCalledWith(2);
  });

  it("does not blow up without an onToggle handler", () => {
    render(<TodoList todos={todos} />);
    expect(() => fireEvent.click(screen.getAllByRole("checkbox")[0])).not.toThrow();
  });
});
