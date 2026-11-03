import type { Db } from "./conversations";

type Row = Record<string, any>;
type Result = { data: any; error: { message: string } | null };
export type FakeState = {
  tables: Record<string, Row[]>;
  files: Record<string, { type: string; text: string }>;
};

const KEYS: Record<string, string[]> = {
  conversations: ["id"],
  messages: ["conversation_id", "id"],
  runs: ["id"],
};

/**
 * An in-memory stand-in for the Supabase client: the query-builder calls the persistence layer makes, backed by plain
 * arrays, with the table defaults the migrations set. For unit tests and for the no-keys browser check.
 */
export function fakeDb(
  state: FakeState = { tables: {}, files: {} },
  onChange: () => void = () => {},
) {
  let clock = state.tables.__clock?.[0]?.n ?? 0;
  const tick = () => {
    state.tables.__clock = [{ n: ++clock }];
    return new Date(2026, 10, 3, 0, 0, clock).toISOString();
  };
  const calls: string[] = [];
  const table = (name: string) => (state.tables[name] ??= []);
  const withDefaults = (name: string, row: Row): Row => {
    const now = tick();
    if (name === "conversations")
      return { title: null, status: "regular", created_at: now, updated_at: now, ...row };
    if (name === "messages")
      return { parent_id: null, format: "ai-sdk/v6", created_at: now, ...row };
    return { created_at: now, updated_at: now, verdict: null, ...row };
  };
  const same = (name: string, a: Row, b: Row) => KEYS[name]!.every((k) => a[k] === b[k]);

  const builder = (name: string) => {
    let op: "select" | "insert" | "upsert" | "update" | "delete" = "select";
    let payload: Row | Row[] = {};
    const filters: ((row: Row) => boolean)[] = [];
    const orders: [string, boolean][] = [];
    let max = Infinity;
    let one = false;
    const run = (): Result => {
      calls.push(`${op} ${name}`);
      const rows = table(name);
      if (op === "insert" || op === "upsert") {
        for (const row of [payload].flat()) {
          const at = rows.findIndex((r) => same(name, r, row));
          if (op === "insert" && at >= 0)
            return { data: null, error: { message: "duplicate key" } };
          if (at >= 0) rows[at] = { ...rows[at], ...row, updated_at: tick() };
          else rows.push(withDefaults(name, row));
          if (name === "messages") {
            const chat = table("conversations").find((c) => c.id === (row as Row).conversation_id);
            if (chat) chat.updated_at = tick();
          }
        }
        onChange();
        return { data: null, error: null };
      }
      const hit = rows.filter((r) => filters.every((f) => f(r)));
      if (op === "update") hit.forEach((r) => Object.assign(r, payload, { updated_at: tick() }));
      if (op === "delete") {
        state.tables[name] = rows.filter((r) => !hit.includes(r));
        if (name === "conversations") {
          const gone = new Set(hit.map((r) => r.id));
          state.tables.messages = table("messages").filter((m) => !gone.has(m.conversation_id));
          table("runs").forEach((r) => gone.has(r.conversation_id) && (r.conversation_id = null));
        }
      }
      if (op !== "select") {
        onChange();
        return { data: null, error: null };
      }
      const sorted = [...hit];
      for (const [col, asc] of [...orders].reverse())
        sorted.sort((a, b) => (a[col] < b[col] ? -1 : a[col] > b[col] ? 1 : 0) * (asc ? 1 : -1));
      const out = sorted.slice(0, max).map((r) => ({ ...r }));
      if (one)
        return out[0]
          ? { data: out[0], error: null }
          : { data: null, error: { message: "no rows" } };
      return { data: out, error: null };
    };
    const api: any = {
      select: () => api,
      insert: (row: Row | Row[]) => ((op = "insert"), (payload = row), api),
      upsert: (row: Row | Row[]) => ((op = "upsert"), (payload = row), api),
      update: (patch: Row) => ((op = "update"), (payload = patch), api),
      delete: () => ((op = "delete"), api),
      eq: (col: string, value: unknown) => (filters.push((r) => r[col] === value), api),
      in: (col: string, values: unknown[]) => (filters.push((r) => values.includes(r[col])), api),
      order: (col: string, o?: { ascending?: boolean }) => (
        orders.push([col, o?.ascending ?? true]),
        api
      ),
      limit: (n: number) => ((max = n), api),
      single: () => ((one = true), api),
      then: (resolve: (r: Result) => unknown, reject?: (e: unknown) => unknown) =>
        Promise.resolve().then(run).then(resolve, reject),
    };
    return api;
  };

  const db = {
    from: builder,
    storage: {
      from: () => ({
        upload: async (path: string, body: Blob | string, options?: { contentType?: string }) => {
          state.files[path] = {
            type: options?.contentType ?? "",
            text: typeof body === "string" ? body : await body.text(),
          };
          onChange();
          return { data: { path }, error: null };
        },
        download: async (path: string) => {
          const file = state.files[path];
          return file
            ? { data: new Blob([file.text], { type: file.type }), error: null }
            : { data: null, error: { message: "Object not found" } };
        },
      }),
    },
  };
  return Object.assign(db as unknown as Db, { state, calls });
}
