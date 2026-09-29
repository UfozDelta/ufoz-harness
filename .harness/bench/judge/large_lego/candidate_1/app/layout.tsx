import type { Metadata } from "next";
import "./globals.css";
import AnalyticsScripts from "../components/AnalyticsScripts";
import { CartProvider } from "../lib/cart-context";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Brick Drop — Lego Sets",
  description: "Shop the best Lego sets, delivered to your door.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AnalyticsScripts />
        <CartProvider>
          <header className="site-header">
            <Link href="/" className="site-name">Brick Drop</Link>
            <Link href="/cart">Cart</Link>
          </header>
          {children}
          <footer className="site-footer">
            <p>&copy; {new Date().getFullYear()} Brick Drop. All rights reserved.</p>
          </footer>
        </CartProvider>
      </body>
    </html>
  );
}
