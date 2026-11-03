import { afterEach, describe, expect, test } from "bun:test";
import { NextRequest } from "next/server";

import proxy from "./proxy";

const keys = ["NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "CLERK_SECRET_KEY"] as const;
const saved = keys.map((k) => process.env[k]);
afterEach(() =>
  keys.forEach((k, i) =>
    saved[i] === undefined ? delete process.env[k] : (process.env[k] = saved[i]),
  ),
);

describe("proxy without Clerk keys", () => {
  test("API routes answer 503 with the setup message", async () => {
    keys.forEach((k) => delete process.env[k]);
    for (const path of ["/api/chat", "/api/answer", "/api/py/status"]) {
      const response = proxy(new NextRequest(`http://x${path}`), {} as never) as Response;
      expect(response.status).toBe(503);
      expect(((await response.json()) as { error: string }).error).toContain("CLERK_SECRET_KEY");
    }
  });

  test("pages pass through to the setup screen", () => {
    keys.forEach((k) => delete process.env[k]);
    const response = proxy(new NextRequest("http://x/"), {} as never) as Response;
    expect(response.status).toBe(200);
    expect(response.headers.get("x-middleware-next")).toBe("1");
  });
});
