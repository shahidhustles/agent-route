import { describe, expect, test } from "bun:test";

import { CSV_LIMIT_BYTES, csvSizeError, isStale, isTooLong, nextTab } from "./route-state";

const route = { task: { text: "Write a Python function add(a,b)." } };

describe("stale decision", () => {
  test("no route is never stale", () => expect(isStale(null, "anything")).toBe(false));
  test("same text, even with outer whitespace, keeps the decision", () => {
    expect(isStale(route, "Write a Python function add(a,b).")).toBe(false);
    expect(isStale(route, "  Write a Python function add(a,b).\n")).toBe(false);
  });
  test("an edit invalidates it", () => {
    expect(isStale(route, "Create a Word document with meeting minutes.")).toBe(true);
    expect(isStale(route, "Write a Python function add(a,b)!")).toBe(true);
  });
});

describe("input limits", () => {
  test("long task warning", () => {
    expect(isTooLong("a".repeat(1500))).toBe(false);
    expect(isTooLong("a".repeat(1501))).toBe(true);
  });
  test("csv size", () => {
    expect(csvSizeError({ name: "a.csv", size: CSV_LIMIT_BYTES })).toBeNull();
    expect(csvSizeError({ name: "big.csv", size: 2_040_004 })).toBe("big.csv is 2.0 MB. The limit is 1.0 MB.");
  });
});

describe("tablist keys", () => {
  test("arrows wrap", () => {
    expect(nextTab("ArrowRight", 0, 2)).toBe(1);
    expect(nextTab("ArrowRight", 1, 2)).toBe(0);
    expect(nextTab("ArrowLeft", 0, 3)).toBe(2);
  });
  test("home, end and other keys", () => {
    expect(nextTab("Home", 2, 3)).toBe(0);
    expect(nextTab("End", 0, 3)).toBe(2);
    expect(nextTab("Enter", 0, 3)).toBeNull();
  });
});
