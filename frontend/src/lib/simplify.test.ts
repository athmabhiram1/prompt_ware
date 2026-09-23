import { describe, expect, it } from "vitest";
import {
  FK_TARGETS,
  LEVELS,
  assertAllCited,
  formatCite,
  hasCitation,
  levelLabel,
  obligationMermaid,
  obligationSteps,
  scenarioForTerm,
  type SimplifySentence,
} from "./simplify";

const CLAUSE: SimplifySentence[] = [
  { text: "You must pay rent by the 5th.", cite: { page: 1, start: 0, end: 10 } },
  { text: "Late payment adds a fee.", cite: { page: 1, start: 11, end: 20 } },
  { text: "We send a notice first.", cite: { page: 2, start: 0, end: 8 } },
  { text: "Then eviction can start.", cite: { page: 2, start: 9, end: 18 } },
];

describe("simplify lib", () => {
  it("formats cites as [doc p.X]", () => {
    expect(formatCite({ page: 3, start: 0, end: 5 })).toBe("[doc p.3]");
  });

  it("rejects sentences without a valid cite", () => {
    expect(hasCitation(CLAUSE[0])).toBe(true);
    expect(hasCitation({ text: "nope", cite: { page: 0, start: 5, end: 5 } })).toBe(false);
    expect(() =>
      assertAllCited([...CLAUSE, { text: "uncited", cite: { page: 1, start: 4, end: 4 } }])
    ).toThrow(/lacks a valid/);
  });

  it("maps levels to FK targets", () => {
    expect(LEVELS).toEqual(["5", "8", "10", "pro"]);
    expect(FK_TARGETS).toEqual({ "5": 6, "8": 8.5, "10": 10, pro: null });
    expect(levelLabel("pro")).toContain("Pro");
  });

  it("builds Pay->Late->Notice->Eviction from obligation triples", () => {
    const steps = obligationSteps(CLAUSE);
    expect(steps.map((step) => step.id)).toEqual(["pay", "late", "notice", "eviction"]);
    expect(steps.every((step) => step.grounded)).toBe(true);
    expect(obligationMermaid(steps)).toContain("pay --> late --> notice --> eviction");
  });

  it("falls back to 4 ungrounded rows when text states nothing", () => {
    const steps = obligationSteps([]);
    expect(steps).toHaveLength(4);
    expect(steps.every((step) => !step.grounded)).toBe(true);
  });

  it("grounds glossary scenarios in cited sentences", () => {
    expect(scenarioForTerm("rent", CLAUSE)).toContain("[doc p.1]");
    expect(scenarioForTerm("arbitration", CLAUSE)).toBeNull();
  });
});
