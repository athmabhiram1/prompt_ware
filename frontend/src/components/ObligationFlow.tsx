import { obligationMermaid } from "../lib/simplify";
import type { ObligationStep } from "../lib/simplify";
import { cn } from "../lib/utils";

interface ObligationFlowProps {
  steps: ObligationStep[];
}

// Rental obligation flowchart: Pay -> Late -> Notice -> Eviction rendered as
// an accessible ordered list, with a table fallback + mermaid source.
export function ObligationFlow({ steps }: ObligationFlowProps) {
  const mermaid = obligationMermaid(steps);

  return (
    <section aria-label="Rental obligation flow" className="parchment-card p-5">
      <h2 className="font-bold text-lg text-[#155e54]">What happens if rent is late?</h2>
      <ol aria-label="Obligation stages" className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-stretch">
        {steps.map((step, index) => (
          <li key={step.id} className="flex flex-1 items-stretch gap-2">
            <div
              className={cn(
                "flex-1 rounded-xl border p-3 text-xs",
                step.grounded
                  ? "border-[#155e54]/40 bg-white"
                  : "border-dashed border-[#d4c5a9] bg-[#eae3d2]/30"
              )}
            >
              <p className="font-extrabold uppercase tracking-wider text-[#155e54]">
                {index + 1}. {step.label}
              </p>
              <p className="mt-1 font-medium leading-relaxed text-[#2d261e]">{step.detail}</p>
            </div>
            {index < steps.length - 1 && (
              <span aria-hidden="true" className="hidden self-center font-black text-[#155e54] sm:block">
                →
              </span>
            )}
          </li>
        ))}
      </ol>

      <details className="mt-3 rounded-xl border border-[#d4c5a9]/60 bg-[#fbf9f4] p-3">
        <summary className="cursor-pointer text-xs font-bold text-[#155e54] focus-visible:outline-2 focus-visible:outline-[#155e54]">
          Table fallback + mermaid source
        </summary>
        <table className="mt-2 w-full text-left text-xs text-[#2d261e]">
          <thead>
            <tr className="uppercase text-[10px] tracking-wider">
              <th scope="col" className="py-1 pr-2">Stage</th>
              <th scope="col" className="py-1 pr-2">Detail</th>
              <th scope="col" className="py-1">Grounded</th>
            </tr>
          </thead>
          <tbody>
            {steps.map((step) => (
              <tr key={step.id} className="border-t border-[#d4c5a9]/40">
                <th scope="row" className="py-1 pr-2 font-bold">{step.label}</th>
                <td className="py-1 pr-2 font-medium">{step.detail}</td>
                <td className="py-1 font-bold">{step.grounded ? "yes" : "fallback"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <pre className="mt-2 overflow-x-auto rounded-lg bg-[#2d261e] p-3 text-[11px] text-[#fbf9f4]">
          {mermaid}
        </pre>
      </details>
    </section>
  );
}
