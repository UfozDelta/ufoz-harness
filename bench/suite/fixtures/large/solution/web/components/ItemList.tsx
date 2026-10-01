import type { Item } from "../lib/api-client";

export type ItemListProps = {
  items: Item[];
  emptyLabel?: string;
};

export function ItemList({ items, emptyLabel = "No items yet." }: ItemListProps) {
  if (items.length === 0) {
    return <p data-testid="item-empty">{emptyLabel}</p>;
  }
  return (
    <ul data-testid="item-list">
      {items.map((item) => (
        <li key={item.id} data-testid="item-row" data-sku={item.sku}>
          <a href={`/items/${item.id}`}>{item.name}</a>
          <span data-testid="item-qty">{item.quantity}</span>
        </li>
      ))}
    </ul>
  );
}

export default ItemList;
