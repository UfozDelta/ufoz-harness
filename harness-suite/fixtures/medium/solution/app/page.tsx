import TodoList from "../components/TodoList";
import { formatCount } from "../lib/format";
import { listTodos } from "../lib/todos-store";
import { isValidTitle } from "../lib/validate";

export default function Page() {
  const todos = listTodos();

  return (
    <main>
      <h1>Todos</h1>
      <p>{formatCount(todos.length)}</p>
      <TodoList todos={todos} emptyLabel="Nothing here yet" />
      <p>{isValidTitle("add a todo") ? "Type a title to add it" : "Titles are required"}</p>
    </main>
  );
}
