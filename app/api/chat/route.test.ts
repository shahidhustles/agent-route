import { afterEach, expect, mock, spyOn, test } from "bun:test";

let signedIn = true;
mock.module("@/lib/require-user", () => ({
  rejectAnonymous: async () =>
    signedIn ? null : Response.json({ error: "Sign in to use Relay." }, { status: 401 }),
}));
const { POST } = await import("./route");
const originalFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = originalFetch;
});
const prompt = {
  messages: [{ role: "user", parts: [{ type: "text", text: "Make a sheet" }] }],
  agentMode: true,
  preference: "cheap",
  override: { agent: "spreadsheet", model: "test-model", rerun_of: "previous" },
};
test("agent stream carries tool events and rerun choices without a second client state", async () => {
  const seen: { url: string; body: unknown }[] = [];
  const decision = { agent: "spreadsheet", model: "router-model" };
  spyOn(globalThis, "fetch").mockImplementation(
    Object.assign(
      async (url: Parameters<typeof fetch>[0], options?: Parameters<typeof fetch>[1]) => {
        const path = String(url).split(":8765/")[1];
        seen.push({
          url: path ?? String(url),
          body: options?.body ? JSON.parse(String(options.body)) : undefined,
        });
        if (path === "status") return Response.json({ stopped: null });
        if (path === "route") return Response.json({ decisions: { cheap: decision } });
        if (path === "runs") return Response.json({ id: "new" });
        if (path === "runs/new/events")
          return new Response(
            'data: {"kind":"tool","tool":"read","text":"input.csv","i":0}\n\ndata: {"kind":"done","status":"passed","i":1}\n\n',
          );
        return Response.json({
          id: "new",
          status: "passed",
          result: { final_text: "Done." },
          artifact: null,
        });
      },
      { preconnect: originalFetch.preconnect },
    ),
  );
  const response = await POST(
    new Request("http://localhost/api/chat", { method: "POST", body: JSON.stringify(prompt) }),
  );
  const stream = await response.text();
  expect(stream).toContain('"type":"tool-input-available"');
  expect(stream).toContain('"toolName":"read"');
  expect(stream).toContain('"type":"tool-output-available"');
  expect(stream).toContain('"delta":"Done."');
  expect(seen.find((r) => r.url === "runs")?.body).toMatchObject({
    preference: "cheap",
    model: "test-model",
    agent: "spreadsheet",
    rerun_of: "previous",
  });
});
test("a spend stop becomes readable chat text and makes no paid call", async () => {
  const calls: string[] = [];
  spyOn(globalThis, "fetch").mockImplementation(
    Object.assign(
      async (url: Parameters<typeof fetch>[0]) => {
        calls.push(String(url));
        return Response.json({ stopped: "spend cap USD 0.25" });
      },
      { preconnect: originalFetch.preconnect },
    ),
  );
  const response = await POST(
    new Request("http://localhost/api/chat", { method: "POST", body: JSON.stringify(prompt) }),
  );
  expect(await response.text()).toContain("Live calls are stopped: spend cap USD 0.25");
  expect(calls).toHaveLength(1);
});
test("backend down becomes readable chat text", async () => {
  spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("fetch failed"));
  const response = await POST(
    new Request("http://localhost/api/chat", { method: "POST", body: JSON.stringify(prompt) }),
  );
  expect(await response.text()).toContain("The backend is unavailable");
});

test("a signed-out request is rejected before any backend call", async () => {
  signedIn = false;
  const fetchSpy = spyOn(globalThis, "fetch");
  const response = await POST(new Request("http://x/api/chat", { method: "POST", body: "{}" }));
  signedIn = true;
  expect(response.status).toBe(401);
  expect(fetchSpy).not.toHaveBeenCalled();
});
