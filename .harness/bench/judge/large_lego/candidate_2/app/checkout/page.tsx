"use client";

import Link from "next/link";
import { useState } from "react";
import { useCart } from "../../lib/cart-context";
import { trackPlaceOrder } from "../../lib/analytics";

export default function CheckoutPage() {
  const { lines, total, clearCart } = useCart();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [postalCode, setPostalCode] = useState("");
  const [country, setCountry] = useState("");
  const [placed, setPlaced] = useState(false);

  function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (lines.length === 0) {
      return;
    }
    trackPlaceOrder({ value: total, items: lines.map((l) => l.slug) });
    clearCart();
    setPlaced(true);
  }

  if (placed) {
    return (
      <main>
        <h1>Checkout</h1>
        <p>Thank you! Your order is confirmed.</p>
        <Link href="/">Continue shopping</Link>
      </main>
    );
  }

  if (lines.length === 0) {
    return (
      <main>
        <h1>Checkout</h1>
        <p>Your cart is empty</p>
        <Link href="/">Continue shopping</Link>
      </main>
    );
  }

  return (
    <main>
      <h1>Checkout</h1>
      <p>Total: ${total.toFixed(2)}</p>
      <form onSubmit={onSubmit}>
        <label>
          Full Name
          <input
            name="fullName"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            required
          />
        </label>
        <label>
          Email
          <input
            type="email"
            name="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label>
          Address
          <input
            name="address"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            required
          />
        </label>
        <label>
          City
          <input
            name="city"
            value={city}
            onChange={(e) => setCity(e.target.value)}
            required
          />
        </label>
        <label>
          Postal Code
          <input
            name="postalCode"
            value={postalCode}
            onChange={(e) => setPostalCode(e.target.value)}
            required
          />
        </label>
        <label>
          Country
          <input
            name="country"
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            required
          />
        </label>
        <button type="submit" className="cta">
          Place Order
        </button>
      </form>
    </main>
  );
}
