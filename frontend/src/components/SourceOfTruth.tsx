import type { SourceRow } from "../lib/types";

// Section 1 — the per-document "source-of-truth values" table (the worked-example output shape).
export function SourceOfTruth({ rows }: { rows: SourceRow[] }) {
  if (!rows || rows.length === 0) return null;
  const cols: { key: keyof SourceRow; label: string }[] = [
    { key: "label", label: "Label" },
    { key: "batch_coc", label: "Batch CoC" },
    { key: "sterile_coc", label: "Sterile CoC" },
    { key: "sterile_lot_record", label: "Sterile Lot Record" },
  ];
  return (
    <section data-testid="source-of-truth">
      <h2 className="mb-2 text-base font-bold text-gray-900">
        Source-of-truth values
      </h2>
      <div className="overflow-x-auto rounded-lg border border-gray-300 bg-white">
        <table className="w-full border-collapse text-xs">
          <thead>
            <tr className="bg-gray-100 text-left font-semibold uppercase tracking-wide text-gray-600">
              <th className="px-3 py-2">Field</th>
              {cols.map((c) => (
                <th key={c.key} className="px-3 py-2">
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.field} className="border-t border-gray-200 align-top">
                <td className="px-3 py-2 font-medium text-gray-800">
                  {r.field}
                </td>
                {cols.map((c) => (
                  <td key={c.key} className="px-3 py-2 text-gray-700">
                    {r[c.key] || "—"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
