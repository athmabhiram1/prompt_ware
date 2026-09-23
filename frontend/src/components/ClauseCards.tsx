import { formatCite, scenarioForTerm } from "../lib/simplify";
import type { GlossaryTerm, SimplifyLang, SimplifySentence } from "../lib/simplify";
import { cn } from "../lib/utils";

interface ClauseCardsProps {
  sentences: SimplifySentence[];
  glossary: GlossaryTerm[];
  lang: SimplifyLang;
  onToggleLang: () => void;
}

// Clause cards + EN/हिंदी toggle (summarize-then-translate: English term in
// brackets). Glossary hover = title tooltip + keyboard-operable details with
// definition + 1-sentence doc-grounded scenario.
export function ClauseCards({ sentences, glossary, lang, onToggleLang }: ClauseCardsProps) {
  const hindi = lang === "hi";

  return (
    <section aria-label="Simplified clauses" className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-bold text-lg text-[#155e54]">Clauses in plain words</h2>
        <button
          type="button"
          aria-pressed={hindi}
          aria-label="Toggle Hindi translation"
          onClick={onToggleLang}
          className={cn(
            "rounded-full border px-4 py-1.5 text-xs font-bold uppercase tracking-wider transition-all",
            "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#155e54]",
            hindi
              ? "bg-[#155e54] text-white border-transparent"
              : "bg-[#fbf9f4] text-[#155e54] border-[#d4c5a9] hover:bg-white"
          )}
        >
          {hindi ? "हिंदी ✓" : "EN / हिंदी"}
        </button>
      </div>

      <ol className="space-y-3">
        {sentences.map((sentence) => (
          <li key={`${sentence.cite.page}-${sentence.cite.start}`}>
            <article className="parchment-card p-4">
              <p className="text-sm font-medium leading-relaxed text-[#2d261e]">{sentence.text}</p>
              <p className="mt-2">
                <span className="inline-block rounded-full bg-[#155e54]/10 border border-[#d4c5a9]/60 px-2.5 py-0.5 text-[10px] font-extrabold uppercase tracking-wider text-[#155e54]">
                  {formatCite(sentence.cite)}
                </span>
              </p>
            </article>
          </li>
        ))}
      </ol>

      {glossary.length > 0 && (
        <div className="parchment-card p-4">
          <h3 className="text-xs font-extrabold uppercase tracking-wider text-[#155e54]">
            Glossary {hindi ? "(शब्दावली)" : ""}
          </h3>
          <ul className="mt-2 flex flex-wrap gap-2">
            {glossary.map((entry) => {
              const label = hindi && entry.hi ? `${entry.hi} (${entry.term})` : entry.term;
              const scenario = scenarioForTerm(entry.term, sentences);
              return (
                <li key={entry.term}>
                  <details className="group rounded-xl border border-[#d4c5a9] bg-white px-3 py-1.5 text-xs">
                    <summary
                      title={`${entry.definition}${scenario ? ` — e.g. ${scenario}` : ""}`}
                      className="cursor-pointer font-bold text-[#155e54] focus-visible:outline-2 focus-visible:outline-[#155e54]"
                    >
                      {label}
                    </summary>
                    <p className="mt-1 max-w-60 font-medium text-[#2d261e]">{entry.definition}</p>
                    {scenario && (
                      <p className="mt-1 max-w-60 italic text-[#2d261e]/80">e.g. {scenario}</p>
                    )}
                  </details>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </section>
  );
}
