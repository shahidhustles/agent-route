/** Rules the task page applies before it spends anything. Pure, so `lib/route-state.test.ts` can cover them. */

/** Mirrors ROUTE_FULL in `routing/server.py`: the router reads a task whole up to this length, then only its start and end. */
export const ROUTE_READ_LIMIT = 1500;
/** The backend refuses request bodies over 2 MB. JSON escaping can double a CSV, so the file limit sits at half. */
export const CSV_LIMIT_BYTES = 1_000_000;

/** A decision belongs to the text it was made for. Any edit since then makes it stale. */
export function isStale(route: { task: { text: string } } | null, text: string): boolean {
  return !!route && route.task.text.trim() !== text.trim();
}

export function isTooLong(text: string): boolean {
  return text.trim().length > ROUTE_READ_LIMIT;
}

export function csvSizeError(file: { name: string; size: number }): string | null {
  if (file.size <= CSV_LIMIT_BYTES) return null;
  const mb = (n: number) => (n / 1_000_000).toFixed(1);
  return `${file.name} is ${mb(file.size)} MB. The limit is ${mb(CSV_LIMIT_BYTES)} MB.`;
}

/** Next tab index for an arrow key in a tablist, wrapping at both ends. Null for keys that do nothing. */
export function nextTab(key: string, index: number, count: number): number | null {
  if (key === "ArrowRight") return (index + 1) % count;
  if (key === "ArrowLeft") return (index - 1 + count) % count;
  if (key === "Home") return 0;
  if (key === "End") return count - 1;
  return null;
}
