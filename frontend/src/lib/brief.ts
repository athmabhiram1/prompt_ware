import axios from "axios";

// W3.1 brief/options/ICS — mirrors backend/app/routers/{brief,options,export}.py
// Pydantic schemas as strict TS types. Field names stay identical to backend.
// jsPDF 1-page export pattern (Context7 /parallax/jspdf): doc.text() +
// doc.output("save") — lazy dynamic import with markdown fallback so the
// build stays green without a new dep. ICS VALARM pattern (Context7
// /adamgibbons/ics): setAlarm({action, trigger:{before}})
// -> BEGIN:VALARM/ACTION/TRIGGER:-PT24H/END:VALARM.

export const DISCLAIMER = "Information, not legal advice — verify with advocate";

export interface BriefCite {
  page: number;
  start: number;
  end: number;
  excerpt: string;
  rule_id: string;
}

export interface VerificationRow {
  source: string;
  section: string;
  timestamp: string;
}

export interface BriefResponse {
  markdown: string;
  redline_docx_path: string;
  questions_for_lawyer: string[];
  verification_trail: VerificationRow[];
  cites: BriefCite[];
  disclaimer: string;
}

export type OptionKind = "fight" | "settle" | "exit";

export interface OptionItem {
  kind: OptionKind;
  title: string;
  tradeoffs: string[];
  cost_hint: string;
  time_hint: string;
}

export interface OptionsResponse {
  options: OptionItem[];
  move_out_checklist: string[];
  tds_checklist: string[];
  disclaimer: string;
}

const API_BASE_URL =
  import.meta.env.VITE_API_URL ??
  import.meta.env.VITE_API_BASE_URL ??
  "http://localhost:8000";

const briefClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
});

export function assertBriefCited(markdown: string): void {
  const bullets = markdown.split("\n").filter((ln) => ln.trim().startsWith("-"));
  const bad = bullets.findIndex((ln) => !/\[doc p\.\d+\]/.test(ln));
  if (bad >= 0) {
    throw new Error(`brief output rejected: bullet ${bad} lacks a valid [doc p.X] cite`);
  }
}

export async function fetchBrief(payload: {
  text?: string | null;
  job_id?: string | null;
  premise?: string;
  pincode?: string | null;
}): Promise<BriefResponse> {
  try {
    const res = await briefClient.post<BriefResponse>("/brief", {
      text: payload.text ?? null,
      job_id: payload.job_id ?? null,
      premise: payload.premise ?? "residential",
      pincode: payload.pincode ?? null,
    });
    assertBriefCited(res.data.markdown);
    return res.data;
  } catch (error) {
    if (error instanceof Error && error.message.startsWith("brief output rejected")) {
      throw error;
    }
    throw new Error(
      `Brief request failed. Ensure the backend is running at ${API_BASE_URL}.`
    );
  }
}

export async function fetchOptions(payload: {
  text?: string | null;
  job_id?: string | null;
  monthly_rent?: number;
  premise?: string;
  pincode?: string | null;
}): Promise<OptionsResponse> {
  try {
    const res = await briefClient.post<OptionsResponse>("/options", {
      text: payload.text ?? null,
      job_id: payload.job_id ?? null,
      monthly_rent: payload.monthly_rent ?? 0,
      premise: payload.premise ?? "residential",
      pincode: payload.pincode ?? null,
    });
    return res.data;
  } catch {
    throw new Error(
      `Options request failed. Ensure the backend is running at ${API_BASE_URL}.`
    );
  }
}

export async function downloadIcs(params: {
  job_id?: string;
  title?: string;
  dtstart?: string;
}): Promise<void> {
  try {
    const res = await briefClient.get<Blob>("/export.ics", {
      params: {
        job_id: params.job_id ?? "brief",
        title: params.title ?? "NyayaMitra deadline reminder",
        dtstart: params.dtstart ?? "20260430T100000",
      },
      responseType: "blob",
    });
    const url = URL.createObjectURL(res.data);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "nyayamitra.ics";
    anchor.click();
    URL.revokeObjectURL(url);
  } catch {
    throw new Error(
      `ICS export failed. Ensure the backend is running at ${API_BASE_URL}.`
    );
  }
}

export function downloadBriefMarkdown(markdown: string): void {
  const blob = new Blob([`${DISCLAIMER}\n\n${markdown}`], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "nyayamitra-brief.md";
  anchor.click();
  URL.revokeObjectURL(url);
}
