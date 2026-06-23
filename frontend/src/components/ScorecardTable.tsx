import { useState } from "react";
import type { Check } from "../lib/types";
import { ResultChip } from "./ResultChip";
import { Json } from "./Json";

function CheckRow({ check }: { check: Check }) {
  const [open, setOpen] = useState(false);
  const hasDetail =
    (check.evidence && Object.keys(check.evidence).length > 0) ||
    (check.sub_results && check.sub_results.length > 0);

  return (
    <>
      <tr
        data-testid={`check-row-${check.check_code}`}
        className={`border-t border-gray-200 ${
          hasDetail ? "cursor-pointer hover:bg-gray-50" : ""
        }`}
        onClick={() => hasDetail && setOpen((o) => !o)}
      >
        <td className="px-3 py-2 align-top">
          <div className="flex items-center gap-1.5 font-mono text-sm font-bold text-gray-800">
            {hasDetail && (
              <span className="inline-block w-3 text-gray-400">
                {open ? "▾" : "▸"}
              </span>
            )}
            {check.check_code}
          </div>
        </td>
        <td className="px-3 py-2 align-top text-sm text-gray-800">
          {check.check_name}
        </td>
        <td className="px-3 py-2 align-top">
          <ResultChip result={check.result} />
        </td>
        <td className="px-3 py-2 align-top text-sm text-gray-700">
          {check.reason}
        </td>
      </tr>
      {open && hasDetail && (
        <tr className="bg-gray-50">
          <td colSpan={4} className="px-3 py-3">
            {check.sub_results && check.sub_results.length > 0 && (
              <div className="mb-3">
                <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">
                  Sub-results
                </div>
                <table className="w-full text-sm">
                  <tbody>
                    {check.sub_results.map((s, i) => (
                      <tr key={i} className="border-t border-gray-200">
                        <td className="py-1 pr-3 font-mono text-xs text-gray-600">
                          {s.item ?? (s.ai ? `AI(${s.ai})` : "—")}
                        </td>
                        <td className="py-1 pr-3">
                          <ResultChip result={s.result} />
                        </td>
                        <td className="py-1 text-gray-700">{s.reason ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">
              Evidence
            </div>
            <Json value={check.evidence} />
          </td>
        </tr>
      )}
    </>
  );
}

export function ScorecardTable({ checks }: { checks: Check[] }) {
  const sorted = [...checks].sort((a, b) =>
    a.check_code.localeCompare(b.check_code),
  );
  return (
    <div className="overflow-hidden rounded-lg border border-gray-300 bg-white">
      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-gray-100 text-left text-xs font-semibold uppercase tracking-wide text-gray-600">
            <th className="px-3 py-2">Check</th>
            <th className="px-3 py-2">Name</th>
            <th className="px-3 py-2">Result</th>
            <th className="px-3 py-2">Reason</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((c) => (
            <CheckRow key={c.check_code} check={c} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
