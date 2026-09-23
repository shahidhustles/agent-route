import { describe, expect, test } from "bun:test";
import type { UIMessage } from "ai";

import { latestUserText } from "./routing";

describe("web routing input", () => {
  test("routes the latest user text without assistant metadata", () => {
    const messages = [
      { id: "1", role: "user", parts: [{ type: "text", text: "first" }] },
      { id: "2", role: "assistant", parts: [{ type: "text", text: "reply" }] },
      { id: "3", role: "user", parts: [{ type: "text", text: "route this task" }] },
    ] as UIMessage[];

    expect(latestUserText(messages)).toBe("route this task");
  });

  test("rejects a request without user text", () => {
    expect(() => latestUserText([])).toThrow("Send a text prompt before routing.");
  });
});
