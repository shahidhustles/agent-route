import { describe, expect, test } from "bun:test";

import { MVP_MODEL_PROFILES, PROFILE_VERSION } from "./profiles";
import { loadSavedRun, parseArgs, routeWithModal } from "./demo";

describe("saved review demo", () => {
  test("uses the current profile version and both measured candidates", async () => {
    const saved = await loadSavedRun();
    expect(saved.profile_version).toBe(PROFILE_VERSION);
    expect(saved.candidates).toEqual(["glm-5.3-flash", "deepseek-v4.1-flash"]);
    expect(saved.examples.map((example) => Object.keys(example.execution)[0]).sort()).toEqual([
      "deepseek-v4.1-flash",
      "glm-5.3-flash",
    ]);
    expect(saved.comparison.paid_calls).toBe(0);
  });

  test("parses prepared examples and exact task input", () => {
    expect(parseArgs(["--example", "fast"]).example).toBe("fast");
    expect(parseArgs(["--task", "hello"]).task).toBe("hello");
    expect(parseArgs(["--help"]).help).toBe(true);
    expect(parseArgs(["--live", "--allow-paid-call", "--max-cost-usd", "0.001"])).toMatchObject({
      live: true,
      allowPaidCall: true,
      maxCostUsd: 0.001,
    });
  });

  test("refuses live execution without the separate environment guard", async () => {
    const { runSavedDemo } = await import("./demo");
    await expect(
      runSavedDemo(
        parseArgs(["--example", "fast", "--live", "--allow-paid-call", "--max-cost-usd", "0.001"]),
      ),
    ).rejects.toThrow("DEMO_ALLOW_PAID_CALLS=I_UNDERSTAND");
  });

  test("sends the pasted task unchanged to the Modal router", async () => {
    const originalFetch = globalThis.fetch;
    const originalId = process.env.MODAL_PROXY_TOKEN_ID;
    const originalSecret = process.env.MODAL_PROXY_TOKEN_SECRET;
    let sentBody = "";
    process.env.MODAL_PROXY_TOKEN_ID = "test-id";
    process.env.MODAL_PROXY_TOKEN_SECRET = "test-secret";
    globalThis.fetch = (async (_input, init) => {
      sentBody = String(init?.body);
      return Response.json({ model_slug: "glm-5.3-flash", confidence: 0.81 });
    }) as typeof fetch;
    try {
      const task = "Explain why the checksum changed, using the supplied logs.";
      const result = await routeWithModal("https://test-router.modal.run", {
        user_task: task,
        candidate_models: ["glm-5.3-flash", "deepseek-v4.1-flash"],
        profiles: MVP_MODEL_PROFILES.filter((profile) =>
          ["glm-5.3-flash", "deepseek-v4.1-flash"].includes(profile.model_slug),
        ),
        requires_tools: false,
        input_tokens: 15,
      });
      expect(JSON.parse(sentBody).user_task).toBe(task);
      expect(result.model_slug).toBe("glm-5.3-flash");
    } finally {
      globalThis.fetch = originalFetch;
      if (originalId === undefined) delete process.env.MODAL_PROXY_TOKEN_ID;
      else process.env.MODAL_PROXY_TOKEN_ID = originalId;
      if (originalSecret === undefined) delete process.env.MODAL_PROXY_TOKEN_SECRET;
      else process.env.MODAL_PROXY_TOKEN_SECRET = originalSecret;
    }
  });
});
