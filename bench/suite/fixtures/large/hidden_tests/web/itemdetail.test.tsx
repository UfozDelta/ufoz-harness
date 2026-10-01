// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import ItemDetail from "./components/ItemDetail";
import type { Item } from "./lib/api-client";

afterEach(cleanup);

const inStock: Item = { id: 7, name: "Widget", sku: "W-7", price: 9.5, quantity: 4 };
const empty: Item = { id: 8, name: "Gadget", sku: "G-8", price: 3, quantity: 0 };

describe("ItemDetail", () => {
  it("renders the item name as a heading", () => {
    render(<ItemDetail item={inStock} />);
    expect(screen.getByTestId("item-detail-name").textContent).toBe("Widget");
  });

  it("exposes the id on the wrapper", () => {
    render(<ItemDetail item={inStock} />);
    expect(screen.getByTestId("item-detail").getAttribute("data-id")).toBe("7");
  });

  it("renders sku, price and quantity", () => {
    render(<ItemDetail item={inStock} />);
    expect(screen.getByTestId("item-detail-sku").textContent).toBe("W-7");
    expect(screen.getByTestId("item-detail-price").textContent).toBe("9.5");
    expect(screen.getByTestId("item-detail-quantity").textContent).toBe("4");
  });

  it("flags an item with no quantity left as out of stock", () => {
    render(<ItemDetail item={empty} />);
    expect(screen.getByTestId("item-out-of-stock").textContent).toBe("Out of stock");
  });

  it("shows no out-of-stock notice while stock remains", () => {
    render(<ItemDetail item={inStock} />);
    expect(screen.queryByTestId("item-out-of-stock")).toBeNull();
  });
});
