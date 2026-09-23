import { useId } from "react";
import { LEVELS, levelLabel, type SimplifyLevel } from "../lib/simplify";
import { cn } from "../lib/utils";

interface ReadingSliderProps {
  value: SimplifyLevel;
  onChange: (level: SimplifyLevel) => void;
}

// Accessible grade slider: native range + label + polite live region.
// shadcn-ui pattern (label association, focus-visible ring) without new deps.
export function ReadingSlider({ value, onChange }: ReadingSliderProps) {
  const sliderId = useId();
  const hintId = useId();
  const index = LEVELS.indexOf(value);

  return (
    <section aria-labelledby={`${sliderId}-heading`} className="parchment-card p-5">
      <h2 id={`${sliderId}-heading`} className="font-bold text-lg text-[#155e54]">
        Reading level
      </h2>
      <label
        htmlFor={sliderId}
        className="mt-1 block text-xs font-bold uppercase tracking-wider text-[#2d261e]"
      >
        Grade slider
      </label>
      <input
        id={sliderId}
        data-testid="reading-slider"
        type="range"
        min={0}
        max={LEVELS.length - 1}
        step={1}
        value={index}
        aria-describedby={hintId}
        aria-valuetext={levelLabel(value)}
        onChange={(event) => onChange(LEVELS[Number(event.target.value)] ?? "8")}
        className="mt-3 w-full accent-[#155e54] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#155e54]"
      />
      <div className="mt-2 flex flex-wrap gap-1.5" role="group" aria-label="Reading level presets">
        {LEVELS.map((level) => (
          <button
            key={level}
            type="button"
            aria-pressed={level === value}
            onClick={() => onChange(level)}
            className={cn(
              "rounded-full border px-3 py-1 text-[11px] font-bold transition-all focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#155e54]",
              level === value
                ? "bg-[#155e54] text-white border-transparent"
                : "bg-white text-[#155e54] border-[#d4c5a9] hover:bg-[#eae3d2]/40"
            )}
          >
            {level === "pro" ? "Pro" : `Grade ${level}`}
          </button>
        ))}
      </div>
      <p id={hintId} role="status" aria-live="polite" className="mt-3 text-xs font-semibold text-[#2d261e]">
        {levelLabel(value)}
      </p>
    </section>
  );
}
