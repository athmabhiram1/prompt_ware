import axios from "axios";

// W2.3 CiteGuard Q&A — mirrors backend/app/routers/qa.py Pydantic schema as
// strict TS types + runtime guards. Field names must stay identical to the
// backend. No localStorage/sessionStorage (AGENTS.md).

export type QaMode = "hybrid" | "lexical" | "semantic";

export interface QaCitation {
  page: number;
  span: string;
  start: number;
  end: number;
}

export interface QaAbstain {
  reason: string;
  code: string;
}

export type AuditVerdict = "Supported" | "Unsupported";

export interface AuditRow {
  sentence: string;
  doc_id: string;
  page: number;
  start: number;
  end: number;
  verdict: AuditVerdict;
  overlap: number;
  sim: number;
}

export interface QaRequest {
  question: string;
  doc_id?: string | null;
  job_id?: string | null;
  mode?: QaMode;
}

export interface QaResponse {
  answer: string | null;
  citations: QaCitation[];
  abstain: QaAbstain | null;
  audit: AuditRow[];
  retrieval_confidence: number;
  support_ratio: number;
  regens: number;
}

// Same base-URL convention as lib/utils.ts (VITE_API_URL canonical).
const API_BASE_URL =
  import.meta.env.VITE_API_URL ??
  import.meta.env.VITE_API_BASE_URL ??
  "http://localhost:8000";

const qaClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
});

export function formatQaCitation(cite: QaCitation): string {
  return `[doc p.${cite.page}]`;
}

function isValidCitation(cite: QaCitation | undefined): boolean {
  if (!cite) return false;
  return (
    Number.isInteger(cite.page) &&
    cite.page >= 1 &&
    Number.isInteger(cite.start) &&
    Number.isInteger(cite.end) &&
    cite.start >= 0 &&
    cite.end > cite.start &&
    typeof cite.span === "string" &&
    cite.span.length > 0
  );
}

export function isAbstained(response: QaResponse): boolean {
  return response.abstain !== null || response.answer === null;
}

// Abstain UI rendering: explicit notice with reason code (never empty text).
export function renderQa(response: QaResponse): string {
  if (isAbstained(response)) {
    const code = response.abstain?.code ?? "ABSTAIN";
    const reason =
      response.abstain?.reason ??
      "The document does not contain sufficient information to answer this question.";
    return `Unable to answer [${code}]: ${reason}`;
  }
  const cites = response.citations.map(formatQaCitation).join(" ");
  return `${response.answer} ${cites}`.trim();
}

// Client-side rejection: a non-abstained answer with an invalid cite is refused.
export function assertQaCited(response: QaResponse): void {
  if (isAbstained(response)) return;
  const bad = response.citations.findIndex((cite) => !isValidCitation(cite));
  if (bad >= 0 || response.citations.length === 0) {
    throw new Error(`qa output rejected: citation ${bad} is invalid or missing`);
  }
}

export async function askQuestion(payload: QaRequest): Promise<QaResponse> {
  try {
    const response = await qaClient.post<QaResponse>("/qa", {
      question: payload.question,
      doc_id: payload.doc_id ?? null,
      job_id: payload.job_id ?? null,
      mode: payload.mode ?? "hybrid",
    });
    assertQaCited(response.data);
    return response.data;
  } catch (error) {
    if (error instanceof Error && error.message.startsWith("qa output rejected")) {
      throw error;
    }
    throw new Error(
      `QA request failed. Ensure the backend is running at ${API_BASE_URL}.`
    );
  }
}

// Audit-trail line per claim sentence for the Wave 4 abstain demo beat.
export function auditLine(row: AuditRow): string {
  const mark = row.verdict === "Supported" ? "ok" : "FAIL";
  return `[${mark}] p.${row.page} overlap=${row.overlap} sim=${row.sim} :: ${row.sentence}`;
}
