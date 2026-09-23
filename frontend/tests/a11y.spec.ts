import { describe, expect, it } from "vitest";

// a11y gate stub (W2.1): full @axe-core/playwright lands in Wave 3.
// This spec locks the slider/proof-bar contract that axe will verify:
// every simplify sentence cited (proof bar reads 100%), slider levels
// ordered with live-region labels, flowchart always has 4 rows.
import {
  LEVELS,
  assertAllCited,
  levelLabel,
  obligationSteps,
} from "../src/lib/simplify";

describe("a11y stub: simplify slider + proof bar", () => {
  it("slider levels are keyboard-ordered with announced labels", () => {
    expect(LEVELS).toEqual(["5", "8", "10", "pro"]);
    for (const level of LEVELS) {
      expect(levelLabel(level).length).toBeGreaterThan(0);
    }
    // Slider contract: native range 0..3, aria-valuetext = levelLabel,
    // status live region announces changes (see ReadingSlider.tsx).
  });

  it("proof bar can reach 100% cited (client-side rejection otherwise)", () => {
    expect(() =>
      assertAllCited([
        { text: "a", cite: { page: 1, start: 0, end: 1 } },
        { text: "b", cite: { page: 2, start: 0, end: 1 } },
      ])
    ).not.toThrow();
  });

  it("flowchart fallback keeps 4 rows for assistive tech", () => {
    expect(obligationSteps([])).toHaveLength(4);
  });
});
