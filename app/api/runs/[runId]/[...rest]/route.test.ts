import { afterEach, expect, mock, spyOn, test } from "bun:test";

import { fakeDb } from "@/lib/persistence/fake-db";

const db = fakeDb();
let session: { userId: string; db: typeof db } | null = { userId: "user_alice", db };
mock.module("@/lib/supabase/server", () => ({ serverSupabase: async () => session }));
const { GET } = await import("./route");

const get = (runId: string, ...rest: string[]) =>
  GET(new Request("http://x"), { params: Promise.resolve({ runId, rest }) });
const originalFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = originalFetch;
  session = { userId: "user_alice", db };
});
const put = (path: string, text: string, type = "") =>
  db.storage.from("artifacts").upload(path, text, { contentType: type });

test("a saved page image comes from Storage with its own type, and the backend is not asked", async () => {
  await put("user_alice/run-1/preview/deck.pptx/page-1.jpg", "jpeg bytes", "image/jpeg");
  const backend = spyOn(globalThis, "fetch");
  const response = await get("run-1", "preview", "deck.pptx", "page-1.jpg");
  expect(response.headers.get("content-type")).toBe("image/jpeg");
  expect(await response.text()).toBe("jpeg bytes");
  expect(backend).not.toHaveBeenCalled();
});

test("the preview manifest reads manifest.json, and a downloaded file is an attachment", async () => {
  await put("user_alice/run-1/preview/deck.pptx/manifest.json", '{"pages":[]}');
  await put("user_alice/run-1/deck.pptx", "pptx bytes");
  const manifest = await get("run-1", "preview", "deck.pptx");
  expect(manifest.headers.get("content-type")).toBe("application/json");
  expect(await manifest.json()).toEqual({ pages: [] });
  const file = await get("run-1", "file", "deck.pptx");
  expect(file.headers.get("content-disposition")).toBe('attachment; filename="deck.pptx"');
});

test("an HTML view carries the sandbox policy", async () => {
  await put("user_alice/run-1/page.html", "<p>hi</p>");
  const response = await get("run-1", "view", "page.html");
  expect(response.headers.get("content-security-policy")).toContain("sandbox allow-scripts");
  expect(response.headers.get("content-type")).toContain("text/html");
});

test("one user's files are not reachable under another user's id", async () => {
  session = { userId: "user_bob", db };
  globalThis.fetch = (async () => new Response("backend says no", { status: 404 })) as unknown as typeof fetch;
  const response = await get("run-1", "file", "deck.pptx");
  expect(response.status).toBe(404);
});

test("a run that is not in Storage yet is read from the backend", async () => {
  const seen: string[] = [];
  globalThis.fetch = (async (url: string) => {
    seen.push(String(url));
    return new Response("live bytes", { headers: { "content-type": "image/jpeg" } });
  }) as unknown as typeof fetch;
  const response = await get("run-2", "preview", "deck.pptx", "page-1.jpg");
  expect(seen).toEqual(["http://127.0.0.1:8765/runs/run-2/preview/deck.pptx/page-1.jpg"]);
  expect(await response.text()).toBe("live bytes");
});

test("path tricks are refused before any lookup", async () => {
  const backend = spyOn(globalThis, "fetch");
  for (const rest of [
    ["file", ".."],
    ["file", "a/b"],
    ["file", "a", "b", "c"],
    ["preview", "x", "../y"],
  ]) {
    expect((await get("run-1", ...rest)).status).toBe(404);
  }
  expect((await get("..", "file", "x")).status).toBe(404);
  expect(backend).not.toHaveBeenCalled();
});
