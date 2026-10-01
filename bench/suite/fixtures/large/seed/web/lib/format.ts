export function pluralItems(count: number): string {
  return `${count} ${count === 1 ? "item" : "items"}`;
}
