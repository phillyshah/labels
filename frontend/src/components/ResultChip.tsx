import type { CheckResult } from "../lib/types";

const STYLES: Record<string, string> = {
  PASS: "bg-green-100 text-green-900 border-green-300",
  FAIL: "bg-red-100 text-red-900 border-red-300",
  FLAG: "bg-amber-100 text-amber-900 border-amber-300",
  DEFERRED: "bg-gray-200 text-gray-800 border-gray-400",
};

export function ResultChip({ result }: { result: CheckResult | string }) {
  const style = STYLES[result] ?? "bg-gray-200 text-gray-800 border-gray-400";
  return (
    <span
      className={`inline-block rounded border px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ${style}`}
    >
      {result}
    </span>
  );
}
