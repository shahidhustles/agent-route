import { describe, expect, test } from "bun:test";

import type { Run } from "@/lib/api";
import {
  createThreadListAdapter,
  loadMessages,
  removeMessages,
  saveMessage,
} from "./conversations";
import { fakeDb } from "./fake-db";
import { createHistoryAdapter } from "./history";
import { saveRun, saveVerdict } from "./runs";

const format = {
  format: "ai-sdk/v6",
  encode: ({
    message: { id: _id, ...rest },
  }: {
    message: { id: string } & Record<string, unknown>;
  }) => rest,
  decode: (stored: { id: string; parent_id: string | null; content: Record<string, unknown> }) => ({
    parentId: stored.parent_id,
    message: { id: stored.id, ...stored.content },
  }),
  getId: (m: { id: string }) => m.id,
};

describe("conversation list adapter", () => {
  test("creates, lists newest first, renames, archives and deletes", async () => {
    const db = fakeDb();
    const adapter = createThreadListAdapter(db);
    const a = await adapter.initialize("local-1");
    const b = await adapter.initialize("local-2");
    expect(a.remoteId).not.toBe(b.remoteId);
    await adapter.rename(a.remoteId, "Quarterly deck");
    // Saving a message bumps the chat to the top, as the migration's trigger does.
    await saveMessage(db, a.remoteId, {
      id: "m1",
      parent_id: null,
      format: "ai-sdk/v6",
      content: { role: "user" },
    });
    const { threads } = await adapter.list();
    expect(threads.map((t) => [t.remoteId, t.title])).toEqual([
      [a.remoteId, "Quarterly deck"],
      [b.remoteId, undefined],
    ]);
    await adapter.archive(b.remoteId);
    expect((await adapter.fetch(b.remoteId)).status).toBe("archived");
    await adapter.unarchive(b.remoteId);
    await adapter.delete(a.remoteId);
    expect((await adapter.list()).threads.map((t) => t.remoteId)).toEqual([b.remoteId]);
    expect(await loadMessages(db, a.remoteId)).toEqual([]);
  });

  test("a failing insert surfaces as an error instead of a silent empty chat", async () => {
    const db = fakeDb();
    const adapter = createThreadListAdapter(db);
    db.state.tables.conversations = [];
    const original = db.from;
    (db as unknown as { from: unknown }).from = (name: string) => {
      const builder = original(name) as unknown as Record<string, unknown>;
      builder.insert = () => ({
        then: (resolve: (x: unknown) => unknown) =>
          resolve({ data: null, error: { message: "JWT expired" } }),
      });
      return builder;
    };
    await expect(adapter.initialize("x")).rejects.toThrow("Creating the chat failed: JWT expired");
  });
});

describe("message history", () => {
  const thread = (
    db: ReturnType<typeof fakeDb>,
    adapter: ReturnType<typeof createThreadListAdapter>,
  ) => {
    let remoteId: string | undefined;
    return createHistoryAdapter(db, () => ({
      getState: () => ({ remoteId }),
      initialize: async () =>
        remoteId
          ? { remoteId }
          : ((remoteId = (await adapter.initialize("t")).remoteId), { remoteId }),
    })).withFormat!(format as never) as unknown as {
      load(): Promise<{ messages: { parentId: string | null; message: { id: string } }[] }>;
      append(i: unknown): Promise<void>;
      update(i: unknown): Promise<void>;
      delete(i: unknown[]): Promise<void>;
    };
  };
  const user = { id: "u1", role: "user", parts: [{ type: "text", text: "Make a deck" }] };
  const reply = {
    id: "a1",
    role: "assistant",
    metadata: { runId: "run-1" },
    parts: [
      {
        type: "tool-code",
        toolCallId: "s1",
        state: "output-available",
        input: { text: "Starting" },
      },
      { type: "text", text: "Done" },
    ],
  };

  test("an empty new thread loads nothing and creates no chat", async () => {
    const db = fakeDb();
    const history = thread(db, createThreadListAdapter(db));
    expect(await history.load()).toEqual({ messages: [] });
    expect(db.state.tables.conversations ?? []).toHaveLength(0);
  });

  test("messages round-trip with parts and metadata, in order, and update in place", async () => {
    const db = fakeDb();
    const history = thread(db, createThreadListAdapter(db));
    await history.append({ parentId: null, message: user });
    await history.append({ parentId: "u1", message: { ...reply, parts: [reply.parts[0]] } });
    await history.update({ parentId: "u1", message: reply });
    const loaded = (await history.load()).messages;
    expect(loaded.map((m) => [m.message.id, m.parentId])).toEqual([
      ["u1", null],
      ["a1", "u1"],
    ]);
    expect(loaded[1]!.message).toEqual(reply);
    expect(db.state.tables.messages).toHaveLength(2);
    expect(db.state.tables.messages![0]!.message).toEqual({ role: "user", parts: user.parts });
  });

  test("deleting a message re-parents its children", async () => {
    const db = fakeDb();
    const adapter = createThreadListAdapter(db);
    const { remoteId } = await adapter.initialize("t");
    for (const [id, parent] of [
      ["a", null],
      ["b", "a"],
      ["c", "b"],
    ] as const)
      await saveMessage(db, remoteId, { id, parent_id: parent, format: "ai-sdk/v6", content: {} });
    await removeMessages(db, remoteId, ["b"]);
    expect((await loadMessages(db, remoteId)).map((m) => [m.id, m.parent_id])).toEqual([
      ["a", null],
      ["c", "a"],
    ]);
  });
});

describe("saving a run", () => {
  const run = {
    id: "run-1",
    text: "Make a three slide deck",
    agent: "slides",
    model: "deepseek/deepseek-v4.1-flash",
    preference: "cheap",
    rerun_of: null,
    status: "passed",
    marked: null,
    route: { agent: "slides", model: "deepseek/deepseek-v4.1-flash", reasoning: "vote" },
    result: { status: "passed", cost_usd: 0.0123, wall_s: 41.5 },
    artifact: {
      agent: "slides",
      contract: "files",
      files: { "page.html": "<p>x</p>" },
      binary: { "deck.pptx": 4 },
    },
  } as unknown as Run;
  const manifest = {
    kind: "pptx",
    pages: [
      {
        page: "/api/py/runs/run-1/preview/deck.pptx/page-1.jpg",
        thumb: "/api/py/runs/run-1/preview/deck.pptx/thumb-1.jpg",
      },
    ],
    pdf: "/api/py/runs/run-1/preview/deck.pptx/file.pdf",
    sheets: null,
  };
  const backend =
    (seen: string[], broken: string[] = []) =>
    async (path: string) => {
      seen.push(path);
      if (broken.includes(path)) return new Response("no", { status: 502 });
      if (path === "runs/run-1/preview/deck.pptx") return Response.json(manifest);
      return new Response(`bytes of ${path}`);
    };

  test("uploads files and page images under the user's id and writes the run row", async () => {
    const db = fakeDb();
    const seen: string[] = [];
    const out = await saveRun(db, {
      run,
      userId: "user_alice",
      conversationId: "chat-1",
      messageId: "a1",
      backend: backend(seen),
    });
    expect(out.failed).toEqual([]);
    expect(Object.keys(db.state.files).sort()).toEqual([
      "user_alice/run-1/deck.pptx",
      "user_alice/run-1/page.html",
      "user_alice/run-1/preview/deck.pptx/file.pdf",
      "user_alice/run-1/preview/deck.pptx/manifest.json",
      "user_alice/run-1/preview/deck.pptx/page-1.jpg",
      "user_alice/run-1/preview/deck.pptx/thumb-1.jpg",
    ]);
    expect(db.state.files["user_alice/run-1/deck.pptx"]!.text).toBe(
      "bytes of runs/run-1/file/deck.pptx",
    );
    // The stored manifest points at the Next route that reads Storage, not the backend proxy.
    expect(db.state.files["user_alice/run-1/preview/deck.pptx/manifest.json"]!.text).toContain(
      "/api/runs/run-1/preview/deck.pptx/page-1.jpg",
    );
    expect(db.state.files["user_alice/run-1/preview/deck.pptx/manifest.json"]!.text).not.toContain(
      "/api/py/",
    );
    const [row] = db.state.tables.runs!;
    expect(row).toMatchObject({
      id: "run-1",
      conversation_id: "chat-1",
      message_id: "a1",
      prompt: "Make a three slide deck",
      agent: "slides",
      preference: "cheap",
      status: "passed",
      cost_usd: 0.0123,
      wall_s: 41.5,
      verdict: null,
    });
    expect(row!.routing).toEqual(run.route);
    expect(row!.artifact).toEqual(run.artifact);
    expect(row!.files).toHaveLength(6);
    expect(row).not.toHaveProperty("user_id");
  });

  test("a failed preview is reported and the run row still saves", async () => {
    const db = fakeDb();
    const out = await saveRun(db, {
      run,
      userId: "u",
      conversationId: null,
      messageId: null,
      backend: backend([], ["runs/run-1/preview/deck.pptx"]),
    });
    expect(out.failed).toEqual(["deck.pptx preview: runs/run-1/preview/deck.pptx: HTTP 502"]);
    expect(db.state.files["u/run-1/deck.pptx"]).toBeDefined();
    expect(db.state.tables.runs).toHaveLength(1);
  });

  test("saving twice keeps one row, and a verdict updates it", async () => {
    const db = fakeDb();
    const input = { run, userId: "u", conversationId: null, messageId: null, backend: backend([]) };
    await saveRun(db, input);
    await saveRun(db, input);
    await saveVerdict(db, "run-1", false);
    expect(db.state.tables.runs).toHaveLength(1);
    expect(db.state.tables.runs![0]!.verdict).toBe(false);
  });

  test("a run with no files, like a failed one, still records its row", async () => {
    const db = fakeDb();
    const failedRun = { ...run, status: "error", artifact: null } as Run;
    await saveRun(db, {
      run: failedRun,
      userId: "u",
      conversationId: null,
      messageId: null,
      backend: backend([]),
    });
    expect(db.state.tables.runs![0]).toMatchObject({ status: "error", artifact: null, files: [] });
    expect(Object.keys(db.state.files)).toEqual([]);
  });
});
