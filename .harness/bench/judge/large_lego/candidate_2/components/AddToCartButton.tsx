"use client";

import { useState } from "react";
import { useCart } from "../lib/cart-context";
import { trackAddToCart } from "../lib/analytics";
import type { Product } from "../lib/products";

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
