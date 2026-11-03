import { expect, test } from "bun:test";
import { sse } from "./chat-stream";

test("SSE preserves events across arbitrary UTF-8 network boundaries", async () => {
  const bytes = new TextEncoder().encode(
    ': heartbeat\n\ndata: {"text":"hello 🌍"}\n\ndata: {"type":"done"}\n\ndata: [DONE]\n\n',
  );
  const response = new Response(
    new ReadableStream({
      start(controller) {
        for (const byte of bytes) controller.enqueue(new Uint8Array([byte]));
        controller.close();
      },
    }),
  );
  const events = [];
  for await (const event of sse(response)) events.push(event);
  expect(events).toEqual([{ text: "hello 🌍" }, { type: "done" }]);
});
test("backend refusal is readable", async () => {
  expect(async () => {
    for await (const event of sse(Response.json({ error: "spend cap" }, { status: 429 })))
      void event;
  }).toThrow("spend cap");
});
