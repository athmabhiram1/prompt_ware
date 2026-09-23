import axios from "axios";

// Same base-URL convention as lib/utils.ts (VITE_API_URL canonical).
const COMPARE_BASE_URL =
  import.meta.env.VITE_API_URL ??
  import.meta.env.VITE_API_BASE_URL ??
  "http://localhost:8000";

const compareClient = axios.create({
  baseURL: COMPARE_BASE_URL,
  timeout: 120000,
});

export type DeltaLabel =
  | "cosmetic"
  | "clarified"
  | "risk-up"
  | "risk-down"
  | "moved"
  | "deleted"
  | "added"
  | "same";
export type DeltaRisk = "green" | "amber" | "red";
export type CiteSide = "v1" | "v2";
export type PartyImpact = "tenant" | "landlord" | "both";
export type CompareVerdict = "pass" | "caution" | "walkaway";

export type Cite = {
  rule_id: string;
  excerpt: string;
  start: number;
  end: number;
  side: CiteSide;
};

export type Delta = {
  label: DeltaLabel;
  risk: DeltaRisk;
  party_impact: PartyImpact;
  one_liner: string;
  cites: Cite[];
};

export type CompareResponse = {
  deltas: Delta[];
  coverage: { v1: number; v2: number };
  removed_protections: string[];
  verdict: CompareVerdict;
};

/** `redlines.json` schema (legal-redline-tools pattern, mirrors backend). */
export type RedlineItem = {
  clause: string;
  action: "insert" | "delete" | "modify";
  v1_text: string;
  v2_text: string;
  cites: Cite[];
};

export type RedlinesJson = {
  version: string;
  items: RedlineItem[];
};

export const RISK_DOT: Record<DeltaRisk, string> = {
  green: "🟢",
  amber: "🟡",
  red: "🔴",
};

export async function postCompare(
  a: string,
  b: string,
  premise = "residential",
): Promise<CompareResponse> {
  try {
    const res = await compareClient.post<CompareResponse>("/compare", { a, b, premise });
    return res.data;
  } catch (err) {
    throw new Error(`compare request failed: ${err instanceof Error ? err.message : String(err)}`);
  }
}

export async function postRedlineJson(
  a: string,
  b: string,
  premise = "residential",
): Promise<RedlinesJson> {
  try {
    const res = await compareClient.post<RedlinesJson>("/compare/redline", { a, b, premise });
    return res.data;
  } catch (err) {
    throw new Error(`redline request failed: ${err instanceof Error ? err.message : String(err)}`);
  }
}

export async function downloadRedlineDocx(
  a: string,
  b: string,
  premise = "residential",
): Promise<void> {
  try {
    const res = await compareClient.post<Blob>("/compare/export.docx", { a, b, premise }, { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "redline.docx";
    anchor.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    throw new Error(`docx export failed: ${err instanceof Error ? err.message : String(err)}`);
  }
}
