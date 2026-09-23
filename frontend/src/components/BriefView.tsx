import { DISCLAIMER, type BriefResponse } from "../lib/brief";
import { cn } from "../lib/utils";

interface BriefViewProps {
  brief: BriefResponse | null;
  loading?: boolean;
  error?: string | null;
  onExportMarkdown?: () => void;
}

export function DisclaimerBar({ text = DISCLAIMER }: { text?: string }) {
  return (
    <div
      role="note"
      aria-label="Legal disclaimer"
      data-testid="disclaimer-bar"
      className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-2 text-xs font-bold text-amber-900"
    >
      {text}
    </div>
  );
}

export function BriefView({ brief, loading = false, error = null, onExportMarkdown }: BriefViewProps) {
  return (
    <section aria-label="Lawyer brief" data-testid="brief-view" className="space-y-3">
      <DisclaimerBar />
      {loading && (
        <p role="status" aria-live="polite" className="text-xs text-[#8c7e6b]">
          Composing brief from cited W2 outputs…
        </p>
      )}
      {error && (
        <p role="alert" className="rounded-xl border border-red-300 bg-red-50 p-3 text-xs text-red-900">
          {error}
        </p>
      )}
      {!brief && !loading && !error && (
        <p className="text-xs text-[#8c7e6b]">No brief yet. Submit a document to compose the 1-page brief.</p>
      )}
      {brief && (
        <div className="space-y-3">
          <article
            aria-label="Brief markdown"
            className={cn("rounded-2xl border border-[#d4c5a9] bg-[#fbf9f4] p-4 text-xs leading-relaxed")}
          >
            <pre className="whitespace-pre-wrap font-sans">{brief.markdown}</pre>
          </article>
          <div aria-label="Questions for lawyer">
            <h3 className="text-xs font-extrabold uppercase tracking-wider text-[#155e54]">
              Questions for lawyer
            </h3>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-xs">
              {brief.questions_for_lawyer.map((q) => (
                <li key={q.slice(0, 48)}>{q}</li>
              ))}
            </ul>
          </div>
          <div aria-label="Verification trail">
            <h3 className="text-xs font-extrabold uppercase tracking-wider text-[#155e54]">
              Verification trail
            </h3>
            <table className="mt-1 w-full text-left text-xs">
              <thead>
                <tr className="text-[10px] uppercase text-[#8c7e6b]">
                  <th className="pr-2">Source</th>
                  <th className="pr-2">Section</th>
                  <th>Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {brief.verification_trail.map((row, idx) => (
                  <tr key={`${row.source}-${row.section}-${idx}`} className="border-t border-[#d4c5a9]/50">
                    <td className="py-1 pr-2 font-bold">{row.source}</td>
                    <td className="py-1 pr-2">{row.section}</td>
                    <td className="py-1">{row.timestamp}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onExportMarkdown}
              className="h-9 rounded-full bg-[#155e54] px-4 text-xs font-bold uppercase tracking-wider text-white hover:bg-[#84cc16]"
            >
              Export brief (.md)
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
