import ItemList from "../components/ItemList";
import { createApiClient } from "../lib/api-client";
import { pluralItems } from "../lib/format";

export default async function HomePage() {
  const items = await createApiClient().listItems();
  return (
    <main>
      <h1>Items</h1>
      <p data-testid="item-count">{pluralItems(items.length)}</p>
      <ItemList items={items} />
    </main>
  );
}
