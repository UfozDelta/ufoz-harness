export interface Todo {
  id: number;
  title: string;
  done: boolean;
}

let todos: Todo[] = [];
let nextId = 1;

export function resetTodos(): void {
  todos = [];
  nextId = 1;
}

export function listTodos(): Todo[] {
  return todos.map((todo) => ({ ...todo }));
}

export function getTodo(id: number): Todo | null {
  const found = todos.find((todo) => todo.id === id);
  return found ? { ...found } : null;
}

export function addTodo(title: string): Todo {
  const todo: Todo = { id: nextId, title, done: false };
  nextId += 1;
  todos.push(todo);
  return { ...todo };
}

export function toggleTodo(id: number): Todo | null {
  const found = todos.find((todo) => todo.id === id);
  if (!found) return null;
  found.done = !found.done;
  return { ...found };
}

export function removeTodo(id: number): boolean {
  const before = todos.length;
  todos = todos.filter((todo) => todo.id !== id);
  return todos.length !== before;
}
