"use client";

import { useState } from "react";
import type { Product } from "../lib/products";
import { useCart } from "../lib/cart-context";
import { trackAddToCart } from "../lib/analytics";

export default function AddToCartButton({ product }: { product: Product }) {
  const { addItem } = useCart();
  const [added, setAdded] = useState(false);

  function handleClick() {
    addItem(product);
    trackAddToCart(product);
    setAdded(true);
  }

  return (
    <button className="cta" onClick={handleClick}>
      {added ? "Added" : "Add to Cart"}
    </button>
  );
}
