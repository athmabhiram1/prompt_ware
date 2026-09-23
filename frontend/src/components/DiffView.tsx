import { useState } from "react";
import {
  RISK_DOT,
  downloadRedlineDocx,
  postRedlineJson,
  type CompareResponse,
  type Delta,
  type RedlinesJson,
} from "../lib/compare";

type Props = {
  a: string;
  b: string;
  premise?: string;
  result: CompareResponse | null;
};

function citeFor(d: Delta, side: "v1" | "v2"): string {
  const hit = d.cites.find((c) => c.side === side);
  return hit ? hit.excerpt : "—";
}

function clauseFor(d: Delta): string {
  const ids = [...new Set(d.cites.map((c) => c.rule_id))];
  return ids.length > 0 ? ids.join(", ") : "general";
}

export default function DiffView({ a, b, premise = "residential", result }: Props) {
  const [hideCosmetic, setHideCosmetic] = useState(true);
  const [redlines, setRedlines] = useState<RedlinesJson | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!result) return <p className="text-sm text-gray-500">Run a comparison to see the clause matrix.</p>;

  const rows = result.deltas.filter((d) => !(hideCosmetic && (d.label === "cosmetic" || d.label === "same")));

  async function onPreviewRedlines(): Promise<void> {
    try {
      setError(null);
      setRedlines(await postRedlineJson(a, b, premise));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function onExportDocx(): Promise<void> {
    try {
      setError(null);
      await downloadRedlineDocx(a, b, premise);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span>
          Verdict: <strong>{result.verdict}</strong>
        </span>
        <span>
          Coverage v1 {Math.round(result.coverage.v1 * 100)}% · v2 {Math.round(result.coverage.v2 * 100)}%
        </span>
        {result.removed_protections.length > 0 && (
          <span className="text-red-700">🔴 removed: {result.removed_protections.join(", ")}</span>
        )}
        <label className="ml-auto flex items-center gap-1">
          <input type="checkbox" checked={hideCosmetic} onChange={(e) => setHideCosmetic(e.target.checked)} />
          Hide cosmetic
        </label>
        <button type="button" className="rounded border px-2 py-1" onClick={onPreviewRedlines}>
          Preview redlines.json
        </button>
        <button type="button" className="rounded border px-2 py-1" onClick={onExportDocx}>
          Export .docx
        </button>
      </div>
      {error && <p className="text-sm text-red-700">{error}</p>}
      <table className="w-full table-fixed border-collapse text-sm">
        <thead>
          <tr className="bg-gray-100">
            <th className="w-28 border p-2 text-left">Clause</th>
            <th className="border p-2 text-left">v1</th>
            <th className="border p-2 text-left">v2</th>
            <th className="w-64 border p-2 text-left">Δ delta</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((d, i) => (
            <tr key={`${clauseFor(d)}-${i}`} className="align-top">
              <td className="border p-2 font-mono text-xs">{clauseFor(d)}</td>
              <td className="border p-2 text-xs">{citeFor(d, "v1")}</td>
              <td className="border p-2 text-xs">{citeFor(d, "v2")}</td>
              <td className="border p-2 text-xs">
                <span className="mr-1">{RISK_DOT[d.risk]}</span>
                <strong>{d.label}</strong> · {d.party_impact}
                <br />
                {d.one_liner}
              </td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={4} className="border p-2 text-center text-gray-500">
                No material deltas — versions are equivalent.
              </td>
            </tr>
          )}
        </tbody>
      </table>
      {redlines && (
        <details className="text-xs">
          <summary>redlines.json ({redlines.items.length} items)</summary>
          <pre className="overflow-auto rounded bg-gray-50 p-2">{JSON.stringify(redlines, null, 2)}</pre>
        </details>
      )}
    </div>
  );
}
