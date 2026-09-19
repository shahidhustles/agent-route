import { describe, expect, test } from "bun:test";

import { PROFILE_VERSION } from "./profiles";
import { loadSavedRun, parseArgs } from "./demo";

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
});
