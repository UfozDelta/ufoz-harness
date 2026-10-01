import { formatCount } from "../lib/format";

export default function Page() {
  return (
    <main>
      <h1>Todos</h1>
      <p>{formatCount(0)}</p>
    </main>
  );
}
