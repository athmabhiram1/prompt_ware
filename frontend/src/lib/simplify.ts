import axios from "axios";

// Zod-mirror note: zod is not a dependency (budget 6.09MB), so this module
// mirrors backend/app/routers/simplify.py Pydantic schema as strict TS
// types + runtime guards. Field names must stay identical to the backend.

export type SimplifyLevel = "5" | "8" | "10" | "pro";
export type SimplifyLang = "en" | "hi";

export interface Cite {
  page: number;
  start: number;
  end: number;
}

export interface SimplifySentence {
  text: string;
  cite: Cite;
}

export interface ReadScores {
  fk: number;
  fre: number;
}

export interface GlossaryTerm {
  term: string;
  definition: string;
  hi: string;
}

export interface SimplifyRequest {
  doc_id?: string | null;
  text?: string | null;
  level: SimplifyLevel;
  lang: SimplifyLang;
}

export interface SimplifyResponse {
  sentences: SimplifySentence[];
  before: ReadScores;
  after: ReadScores;
  glossary: GlossaryTerm[];
  level: string;
  lang: string;
}

export interface ObligationStep {
  id: "pay" | "late" | "notice" | "eviction";
  label: string;
  detail: string;
  grounded: boolean;
}

export const LEVELS: SimplifyLevel[] = ["5", "8", "10", "pro"];

// W2.1: FK targets mirror backend FK_LEVEL_TARGETS (null = pro, unchanged).
export const FK_TARGETS: Record<SimplifyLevel, number | null> = {
  "5": 6,
  "8": 8.5,
  "10": 10,
  pro: null,
};

export function levelLabel(level: SimplifyLevel): string {
  if (level === "pro") return "Pro (legal terms kept)";
  return `Grade ${level} (FK ≤ ${FK_TARGETS[level]})`;
}

// Same base-URL convention as lib/utils.ts (VITE_API_URL canonical).
const API_BASE_URL =
  import.meta.env.VITE_API_URL ??
  import.meta.env.VITE_API_BASE_URL ??
  "http://localhost:8000";

const simplifyClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
});

export function formatCite(cite: Cite): string {
  return `[doc p.${cite.page}]`;
}

function isValidCite(cite: Cite | undefined): boolean {
  if (!cite) return false;
  return (
    Number.isInteger(cite.page) &&
    cite.page >= 1 &&
    Number.isInteger(cite.start) &&
    Number.isInteger(cite.end) &&
    cite.start >= 0 &&
    cite.end > cite.start
  );
}

export function hasCitation(sentence: SimplifySentence): boolean {
  return sentence.text.length > 0 && isValidCite(sentence.cite);
}

// Client-side rejection: output with an uncited sentence is refused.
export function assertAllCited(sentences: SimplifySentence[]): void {
  const bad = sentences.findIndex((item) => !hasCitation(item));
  if (bad >= 0) {
    throw new Error(`simplify output rejected: sentence ${bad} lacks a valid [doc p.X] cite`);
  }
}

export async function simplifyDocument(payload: SimplifyRequest): Promise<SimplifyResponse> {
  try {
    const response = await simplifyClient.post<SimplifyResponse>("/simplify", payload);
    assertAllCited(response.data.sentences);
    return response.data;
  } catch (error) {
    if (error instanceof Error && error.message.startsWith("simplify output rejected")) {
      throw error;
    }
    throw new Error(
      `Simplify request failed. Ensure the backend is running at ${API_BASE_URL}.`
    );
  }
}

// Doc-grounded 1-sentence scenario for glossary hover (Wave 3: LLM scenario).
export function scenarioForTerm(term: string, sentences: SimplifySentence[]): string | null {
  const needle = term.toLowerCase();
  const hit = sentences.find((item) => item.text.toLowerCase().includes(needle));
  return hit ? `${hit.text} ${formatCite(hit.cite)}` : null;
}

const OBLIGATION_PATTERNS: { id: ObligationStep["id"]; label: string; test: RegExp }[] = [
  { id: "pay", label: "Pay", test: /\b(pay\w*|rent|due)\b/i },
  { id: "late", label: "Late", test: /\b(late|unpaid|overdue|default)\b/i },
  { id: "notice", label: "Notice", test: /\b(notic\w*|notify|warn\w*)\b/i },
  { id: "eviction", label: "Eviction", test: /\b(evict\w*|vacat\w*|leav\w*|terminat\w*)\b/i },
];

// Canonical Pay -> Late -> Notice -> Eviction flow; missing stages render
// ungrounded so the table fallback always has 4 rows (never an empty chart).
export function obligationSteps(sentences: SimplifySentence[]): ObligationStep[] {
  return OBLIGATION_PATTERNS.map((pattern) => {
    const hit = sentences.find((item) => pattern.test.test(item.text));
    return {
      id: pattern.id,
      label: pattern.label,
      detail: hit ? `${hit.text} ${formatCite(hit.cite)}` : `${pattern.label} stage not stated in text.`,
      grounded: hit !== undefined,
    };
  });
}

export function obligationMermaid(steps: ObligationStep[]): string {
  const chain = steps.map((step) => step.id).join(" --> ");
  return `flowchart LR\n    ${chain}`;
}
