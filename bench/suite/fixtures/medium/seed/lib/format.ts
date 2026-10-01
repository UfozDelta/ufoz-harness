export function formatCount(n: number): string {
  return `${n} ${n === 1 ? "todo" : "todos"}`;
}
