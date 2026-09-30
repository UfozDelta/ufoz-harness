import { addTodo, listTodos } from "../../../lib/todos-store";

const MAX_TITLE = 120;

export async function GET(): Promise<Response> {
  return Response.json(listTodos());
}

export async function POST(request: Request): Promise<Response> {
  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return Response.json({ error: "invalid JSON body" }, { status: 400 });
  }

  const raw = (payload as { title?: unknown } | null)?.title;
  if (typeof raw !== "string") {
    return Response.json({ error: "title is required" }, { status: 400 });
  }
  const title = raw.trim();
  if (title.length === 0 || title.length > MAX_TITLE) {
    return Response.json({ error: "title must be 1-120 characters" }, { status: 400 });
  }

  const todo = addTodo(title);
  return Response.json(todo, { status: 201 });
}
