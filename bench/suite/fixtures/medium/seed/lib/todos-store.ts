// Stub: the plan's task replaces this file with the real implementation.
export interface Todo {
  id: number;
  title: string;
  done: boolean;
}

export function resetTodos(): void {
  throw new Error("not implemented");
}

export function listTodos(): Todo[] {
  throw new Error("not implemented");
}

export function getTodo(id: number): Todo | null {
  throw new Error("not implemented");
}

export function addTodo(title: string): Todo {
  throw new Error("not implemented");
}

export function toggleTodo(id: number): Todo | null {
  throw new Error("not implemented");
}

export function removeTodo(id: number): boolean {
  throw new Error("not implemented");
}
