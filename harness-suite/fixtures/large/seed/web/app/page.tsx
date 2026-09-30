import { pluralItems } from "../lib/format";

export default function HomePage() {
  return (
    <main>
      <h1>Items</h1>
      <p data-testid="item-count">{pluralItems(0)}</p>
    </main>
  );
}
