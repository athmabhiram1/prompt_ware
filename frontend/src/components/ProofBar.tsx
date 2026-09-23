import type { ReadScores } from "../lib/simplify";
import { cn } from "../lib/utils";

interface ProofBarProps {
  before: ReadScores;
  after: ReadScores;
  total: number;
  cited: number;
}

// FK/FRE proof bar: aria-live announces score changes to screen readers.
export function ProofBar({ before, after, total, cited }: ProofBarProps) {
  const coverage = total === 0 ? 0 : Math.round((cited / total) * 100);
  const fkDelta = after.fk - before.fk;
  const complete = total > 0 && cited === total;

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="proof-bar"
      className={cn(
        "rounded-2xl border p-4 text-xs font-semibold",
        complete
          ? "border-[#d4c5a9] bg-[#fbf9f4] text-[#2d261e]"
          : "border-red-300 bg-red-50 text-red-900"
      )}
    >
      <p className="font-bold uppercase tracking-wider text-[#155e54]">
        Proof: every sentence cited
      </p>
      <dl className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <div>
          <dt className="uppercase text-[10px]">FK before</dt>
          <dd className="text-base font-extrabold">{before.fk.toFixed(1)}</dd>
        </div>
        <div>
          <dt className="uppercase text-[10px]">FK after</dt>
          <dd className="text-base font-extrabold">{after.fk.toFixed(1)}</dd>
        </div>
        <div>
          <dt className="uppercase text-[10px]">FRE after</dt>
          <dd className="text-base font-extrabold">{after.fre.toFixed(1)}</dd>
        </div>
        <div>
          <dt className="uppercase text-[10px]">Cited</dt>
          <dd className="text-base font-extrabold">
            {cited}/{total} ({coverage}%)
          </dd>
        </div>
      </dl>
      <p className="mt-2">
        {complete
          ? `Reading ease improved by ${fkDelta <= 0 ? `${Math.abs(fkDelta).toFixed(1)} grades` : "kept (pro level)"}; 100% sentences carry [doc p.X].`
          : `Rejected: ${total - cited} sentence(s) missing [doc p.X] — output refused client-side.`}
      </p>
    </div>
  );
}
