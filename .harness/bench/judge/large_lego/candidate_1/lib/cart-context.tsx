"use client";

import { createContext, useContext, useEffect, useState } from "react";
import type { Product } from "./products";
import { products } from "./products";

export const CART_STORAGE_KEY = "lego_cart";

export type CartLine = { slug: string; quantity: number };

export type CartContextValue = {
  lines: CartLine[];
  addItem: (product: Product) => void;
  removeItem: (slug: string) => void;
  clearCart: () => void;
  itemCount: number;
  total: number;
};

const CartContext = createContext<CartContextValue | undefined>(undefined);

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>([]);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(CART_STORAGE_KEY);
      if (stored) setLines(JSON.parse(stored) as CartLine[]);
    } catch {
      // ignore bad data
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    try {
      localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(lines));
    } catch {
      // ignore storage errors
    }
  }, [lines, hydrated]);

  function addItem(product: Product) {
    setLines((prev) => {
      const existing = prev.find((l) => l.slug === product.slug);
      if (existing) {
        return prev.map((l) =>
          l.slug === product.slug ? { ...l, quantity: l.quantity + 1 } : l
        );
      }
      return [...prev, { slug: product.slug, quantity: 1 }];
    });
  }

  function removeItem(slug: string) {
    setLines((prev) => prev.filter((l) => l.slug !== slug));
  }

  function clearCart() {
    setLines([]);
  }

  const itemCount = lines.reduce((sum, l) => sum + l.quantity, 0);
  const total = Math.round(
    lines.reduce((sum, l) => {
      const product = products.find((p) => p.slug === l.slug);
      return sum + (product ? product.price * l.quantity : 0);
    }, 0) * 100
  ) / 100;

  return (
    <CartContext.Provider value={{ lines, addItem, removeItem, clearCart, itemCount, total }}>
      {children}
    </CartContext.Provider>
  );
}

export function useCart(): CartContextValue {
  const context = useContext(CartContext);
  if (!context) throw new Error("useCart must be used within CartProvider");
  return context;
}
