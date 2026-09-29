import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { CartProvider } from "../lib/cart-context";
import AnalyticsScripts from "../components/AnalyticsScripts";

export const metadata: Metadata = {
  title: "Brick Drop — Lego Sets",
  description: "Shop Lego sets at Brick Drop.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AnalyticsScripts />
        <CartProvider>
          <header>
            <Link href="/">Brick Drop</Link>
            <nav>
              <Link href="/cart">Cart</Link>
            </nav>
          </header>
          {children}
          <footer>
            <p>Brick Drop — Lego sets for builders of all ages.</p>
          </footer>
        </CartProvider>
      </body>
    </html>
  );
}
