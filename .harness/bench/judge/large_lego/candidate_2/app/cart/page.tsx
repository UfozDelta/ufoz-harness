"use client";

import Link from "next/link";
import { useCart } from "../../lib/cart-context";
import { getProduct } from "../../lib/products";

export default function CartPage() {
  const { lines, removeItem, total } = useCart();

  if (lines.length === 0) {
    return (
      <main>
        <h1>Cart</h1>
        <p>Your cart is empty</p>
        <Link href="/">Continue shopping</Link>
      </main>
    );
  }

  return (
    <main>
      <h1>Cart</h1>
      <ul>
        {lines.map((line) => {
          const product = getProduct(line.slug);
          if (!product) {
            return null;
          }
          return (
            <li key={line.slug}>
              <span>{product.name}</span>
              <span>Qty: {line.quantity}</span>
              <span>${(product.price * line.quantity).toFixed(2)}</span>
              <button onClick={() => removeItem(line.slug)}>Remove</button>
            </li>
          );
        })}
      </ul>
      <p>Total: ${total.toFixed(2)}</p>
      <Link href="/checkout" className="cta">
        Checkout
      </Link>
    </main>
  );
}
