"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { products, type Product } from "./products";

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

const CartContext = createContext<CartContextValue | null>(null);

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>([]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(CART_STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          setLines(parsed);
        }
      }
    } catch {
      // ignore bad data
    }
  }, []);

  useEffect(() => {
    localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(lines));
  }, [lines]);

  function addItem(product: Product): void {
    setLines((prev) => {
      const existing = prev.find((line) => line.slug === product.slug);
      if (existing) {
        return prev.map((line) =>
          line.slug === product.slug ? { ...line, quantity: line.quantity + 1 } : line,
        );
      }
      return [...prev, { slug: product.slug, quantity: 1 }];
    });
  }

  function removeItem(slug: string): void {
    setLines((prev) => prev.filter((line) => line.slug !== slug));
  }

  function clearCart(): void {
    setLines([]);
  }

  const itemCount = lines.reduce((sum, line) => sum + line.quantity, 0);

  const total = Math.round(
    lines.reduce((sum, line) => {
      const product = products.find((p) => p.slug === line.slug);
      if (!product) {
        return sum;
      }
      return sum + product.price * line.quantity;
    }, 0) * 100,
  ) / 100;

  const value: CartContextValue = {
    lines,
    addItem,
    removeItem,
    clearCart,
    itemCount,
    total,
  };

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartContextValue {
  const ctx = useContext(CartContext);
  if (!ctx) {
    throw new Error("useCart must be used within CartProvider");
  }
  return ctx;
}
