"use client";

import { useState } from "react";
import { useCart } from "../../lib/cart-context";
import { trackPlaceOrder } from "../../lib/analytics";

type ShippingForm = {
  fullName: string;
  email: string;
  address: string;
  city: string;
  postalCode: string;
  country: string;
};

const EMPTY_FORM: ShippingForm = {
  fullName: "",
  email: "",
  address: "",
  city: "",
  postalCode: "",
  country: "",
};

export default function CheckoutPage() {
  const { lines, total, clearCart } = useCart();
  const [form, setForm] = useState<ShippingForm>(EMPTY_FORM);
  const [placed, setPlaced] = useState(false);

  function handleChange(field: keyof ShippingForm) {
    return (e: React.ChangeEvent<HTMLInputElement>) => {
      setForm((prev) => ({ ...prev, [field]: e.target.value }));
    };
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    trackPlaceOrder({ value: total, items: lines.map((l) => l.slug) });
    clearCart();
    setPlaced(true);
  }

  if (placed) {
    return (
      <main className="container">
        <h1>Checkout</h1>
        <p>Thank you! Your order is confirmed.</p>
      </main>
    );
  }

  if (lines.length === 0) {
    return (
      <main className="container">
        <h1>Checkout</h1>
        <p>Your cart is empty.</p>
      </main>
    );
  }

  return (
    <main className="container">
      <h1>Checkout</h1>
      <p>Order total: ${total.toFixed(2)}</p>
      <form onSubmit={handleSubmit}>
        <input
          required
          placeholder="Full name"
          value={form.fullName}
          onChange={handleChange("fullName")}
        />
        <input
          required
          type="email"
          placeholder="Email"
          value={form.email}
          onChange={handleChange("email")}
        />
        <input
          required
          placeholder="Address"
          value={form.address}
          onChange={handleChange("address")}
        />
        <input required placeholder="City" value={form.city} onChange={handleChange("city")} />
        <input
          required
          placeholder="Postal code"
          value={form.postalCode}
          onChange={handleChange("postalCode")}
        />
        <input
          required
          placeholder="Country"
          value={form.country}
          onChange={handleChange("country")}
        />
        <button type="submit" className="cta">
          Place Order
        </button>
      </form>
    </main>
  );
}
