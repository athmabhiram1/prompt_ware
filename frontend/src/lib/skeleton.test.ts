import { describe, expect, it } from "vitest";

// Day-1 skeleton gate (W1.5): proves `npm test` (vitest run) is wired.
// Wave 2 adds real suites (rule/QA/a11y) — this file stays tiny.
describe("ci skeleton", () => {
  it("boots the test runner", () => {
    expect(1 + 1).toBe(2);
  });
});
