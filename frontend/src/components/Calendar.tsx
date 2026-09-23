import { useState } from "react";
import { DISCLAIMER, downloadIcs } from "../lib/brief";
import { DisclaimerBar } from "./BriefView";

interface CalendarProps {
  jobId?: string;
}

const DEFAULT_DTSTART = "20260430T100000";

export function Calendar({ jobId = "brief" }: CalendarProps) {
  const [title, setTitle] = useState("TDS filing reminder (26QC)");
  const [dtstart, setDtstart] = useState(DEFAULT_DTSTART);
  const [status, setStatus] = useState<string | null>(null);

  async function handleDownload(): Promise<void> {
    setStatus(null);
    try {
      await downloadIcs({ job_id: jobId, title, dtstart });
      setStatus("Calendar file downloaded — import nyayamitra.ics into Google Calendar.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "ICS export failed.");
    }
  }

  return (
    <section aria-label="Deadline calendar" data-testid="calendar" className="space-y-3">
      <DisclaimerBar text={DISCLAIMER} />
      <div className="rounded-2xl border border-[#d4c5a9] bg-[#fbf9f4] p-4 text-xs">
        <h3 className="font-extrabold uppercase tracking-wider text-[#155e54]">
          Deadlines → calendar (VEVENT + VALARM)
        </h3>
        <label htmlFor="calendar-title" className="mt-3 block font-bold text-[#8c7e6b]">
          Event title
        </label>
        <input
          id="calendar-title"
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="mt-1 w-full rounded-xl border border-[#d4c5a9] bg-white px-3 py-2 text-xs font-bold text-[#155e54]"
        />
        <label htmlFor="calendar-dtstart" className="mt-3 block font-bold text-[#8c7e6b]">
          Start (RFC5545 DTSTART, e.g. 20260430T100000)
        </label>
        <input
          id="calendar-dtstart"
          type="text"
          value={dtstart}
          onChange={(e) => setDtstart(e.target.value)}
          pattern="\d{8}T\d{6}"
          className="mt-1 w-full rounded-xl border border-[#d4c5a9] bg-white px-3 py-2 text-xs font-bold text-[#155e54]"
        />
        <button
          type="button"
          onClick={() => void handleDownload()}
          className="mt-3 h-9 rounded-full bg-[#155e54] px-4 text-xs font-bold uppercase tracking-wider text-white hover:bg-[#84cc16]"
        >
          Download .ics (24h reminder)
        </button>
        {status && (
          <p role="status" aria-live="polite" className="mt-2 text-xs text-[#155e54]">
            {status}
          </p>
        )}
      </div>
    </section>
  );
}
