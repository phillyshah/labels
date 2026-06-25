import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { SubmissionListItem, Verdict } from "../lib/types";
import { ApiError, listSubmissions } from "../lib/api";
import { ResultChip } from "../components/ResultChip";

const VERDICT_CHIP: Record<Verdict, string> = {
  APPROVE: "PASS",
  APPROVE_WITH_FLAGS: "FLAG",
  REJECT: "FAIL",
};

export function History() {
  const [rows, setRows] = useState<SubmissionListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    listSubmissions()
      .then((r) => active && setRows(r))
      .catch(
        (e) =>
          active &&
          setError(e instanceof ApiError ? e.message : "could not load history"),
      );
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="mb-4 text-xl font-bold text-gray-900">History</h1>

      {error && (
        <div className="mb-4 rounded border border-red-300 bg-red-50 p-4 text-sm text-red-900">
          {error}
        </div>
      )}

      <div className="overflow-hidden rounded-lg border border-gray-300 bg-white">
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-gray-100 text-left text-xs font-semibold uppercase tracking-wide text-gray-600">
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2">REF</th>
              <th className="px-3 py-2">LOT</th>
              <th className="px-3 py-2">Sterile lot</th>
              <th className="px-3 py-2">Verdict</th>
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows === null ? (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center text-gray-500">
                  Loading…
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center text-gray-500">
                  No submissions yet.
                </td>
              </tr>
            ) : (
              rows.map((r) => (
                <tr
                  key={r.id}
                  className="border-t border-gray-200 hover:bg-gray-50"
                >
                  <td className="px-3 py-2 text-sm">
                    <Link
                      to={`/submissions/${r.id}`}
                      className="font-medium text-blue-700 hover:underline"
                    >
                      {new Date(r.created_at).toLocaleString()}
                    </Link>
                  </td>
                  <td className="px-3 py-2 font-mono text-sm text-gray-800">
                    {r.ref ?? "—"}
                  </td>
                  <td className="px-3 py-2 font-mono text-sm text-gray-800">
                    {r.lot ?? "—"}
                  </td>
                  <td className="px-3 py-2 font-mono text-sm text-gray-800">
                    {r.sterile_lot ?? "—"}
                  </td>
                  <td className="px-3 py-2">
                    {r.verdict ? (
                      <ResultChip result={VERDICT_CHIP[r.verdict]} />
                    ) : (
                      <span className="text-sm text-gray-400">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-sm capitalize text-gray-700">
                    {r.status}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
