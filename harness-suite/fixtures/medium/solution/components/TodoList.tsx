"use client";

import type { Todo } from "../lib/todos-store";

export interface TodoListProps {
  todos: Todo[];
  onToggle?: (id: number) => void;
  emptyLabel?: string;
}

export default function TodoList({ todos, onToggle, emptyLabel = "No todos yet" }: TodoListProps) {
  if (todos.length === 0) {
    return <p data-testid="todo-empty">{emptyLabel}</p>;
  }

  return (
    <ul data-testid="todo-list">
      {todos.map((todo) => (
        <li key={todo.id} data-testid={`todo-${todo.id}`}>
          <label>
            <input
              type="checkbox"
              checked={todo.done}
              aria-label={todo.title}
              onChange={() => onToggle?.(todo.id)}
            />
            <span>{todo.title}</span>
          </label>
        </li>
      ))}
    </ul>
  );
}
