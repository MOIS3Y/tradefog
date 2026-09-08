/** Shared primitives for stable client-side table sorting. */

export type SortDirection = "asc" | "desc";

const collator = new Intl.Collator(undefined, {
  numeric: true,
  sensitivity: "base",
});

export function compareText(
  left: string | null,
  right: string | null,
  direction: SortDirection,
): number {
  if (left === null) {
    return right === null ? 0 : 1;
  }
  if (right === null) {
    return -1;
  }
  const result = collator.compare(left, right);
  return direction === "asc" ? result : -result;
}
