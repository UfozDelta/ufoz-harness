import type { Item } from "../lib/api-client";

export type ItemDetailProps = {
  item: Item;
};

export function ItemDetail({ item }: ItemDetailProps) {
  return (
    <article data-testid="item-detail" data-id={String(item.id)}>
      <h2 data-testid="item-detail-name">{item.name}</h2>
      <dl>
        <dt>SKU</dt>
        <dd data-testid="item-detail-sku">{item.sku}</dd>
        <dt>Price</dt>
        <dd data-testid="item-detail-price">{item.price}</dd>
        <dt>Quantity</dt>
        <dd data-testid="item-detail-quantity">{item.quantity}</dd>
      </dl>
      {item.quantity === 0 ? <p data-testid="item-out-of-stock">Out of stock</p> : null}
    </article>
  );
}

export default ItemDetail;
