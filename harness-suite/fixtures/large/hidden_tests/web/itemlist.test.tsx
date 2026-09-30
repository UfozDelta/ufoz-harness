// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import ItemList, { type ItemListProps } from "./components/ItemList";
import type { Item } from "./lib/api-client";

afterEach(cleanup);

const items: Item[] = [
  { id: 1, name: "Widget", sku: "W-1", price: 9.5, quantity: 4 },
  { id: 2, name: "Gadget", sku: "G-2", price: 3, quantity: 0 },
];

function renderList(props: ItemListProps) {
  return render(<ItemList {...props} />);
}

describe("ItemList", () => {
  it("shows the default empty label when there are no items", () => {
    renderList({ items: [] });
    expect(screen.getByTestId("item-empty").textContent).toBe("No items yet.");
    expect(screen.queryByTestId("item-list")).toBeNull();
  });

  it("honours a custom empty label", () => {
    renderList({ items: [], emptyLabel: "Nothing in stock." });
    expect(screen.getByTestId("item-empty").textContent).toBe("Nothing in stock.");
  });

  it("renders one row per item, in order", () => {
    renderList({ items });
    const rows = screen.getAllByTestId("item-row");
    expect(rows).toHaveLength(2);
    expect(rows[0]!.textContent).toContain("Widget");
    expect(rows[1]!.textContent).toContain("Gadget");
  });

  it("exposes the sku on every row", () => {
    renderList({ items });
    const rows = screen.getAllByTestId("item-row");
    expect(rows[0]!.getAttribute("data-sku")).toBe("W-1");
    expect(rows[1]!.getAttribute("data-sku")).toBe("G-2");
  });

  it("renders the quantity of every item", () => {
    renderList({ items });
    const quantities = screen.getAllByTestId("item-qty").map((node) => node.textContent);
    expect(quantities).toEqual(["4", "0"]);
  });

  it("links each row to the item detail route", () => {
    renderList({ items });
    const links = screen.getAllByRole("link");
    expect(links[0]!.getAttribute("href")).toBe("/items/1");
    expect(links[1]!.getAttribute("href")).toBe("/items/2");
  });

  it("does not render the empty label when items exist", () => {
    renderList({ items });
    expect(screen.queryByTestId("item-empty")).toBeNull();
    expect(screen.getByTestId("item-list")).not.toBeNull();
  });
});
