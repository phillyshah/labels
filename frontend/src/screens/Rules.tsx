import { useEffect, useState } from "react";
import { health } from "../lib/api";

export function Rules() {
  const [rulesVersion, setRulesVersion] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    health()
      .then((h) => {
        if (!active) return;
        setRulesVersion(h?.rules_version ?? null);
        setStatus(h?.status ?? null);
      })
      .catch(() => active && setStatus("unreachable"));
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="mb-4 text-xl font-bold text-gray-900">Rules</h1>

      <div className="rounded-lg border border-gray-300 bg-white p-5">
        <dl className="grid grid-cols-[auto,1fr] gap-x-6 gap-y-2 text-sm">
          <dt className="font-medium text-gray-600">Active rules version</dt>
          <dd className="font-mono text-gray-900">
            {rulesVersion ?? "loading…"}
          </dd>
          <dt className="font-medium text-gray-600">Backend status</dt>
          <dd className="text-gray-900">{status ?? "loading…"}</dd>
        </dl>
      </div>

      <div className="mt-6 rounded-lg border border-gray-300 bg-gray-50 p-5 text-sm leading-relaxed text-gray-700">
        <h2 className="mb-2 text-base font-bold text-gray-900">
          Deferred checks
        </h2>
        <p>
          Checks <strong>D</strong> (description normalization),{" "}
          <strong>E</strong> (IFU linkage) and <strong>F</strong> (static
          content), together with the <strong>GTIN</strong> portion of the
          barcode check, are <strong>DEFERRED</strong> until the source data is
          supplied:
        </p>
        <ul className="mt-2 list-disc pl-6">
          <li>
            <strong>MXO-PP00001</strong> — Labeling Guidelines (drives D / E /
            F).
          </li>
          <li>
            <strong>MXO-PP00006</strong> — GTIN Codes (drives the GTIN match).
          </li>
        </ul>
        <p className="mt-2">
          Until these are loaded, the dependent checks return{" "}
          <strong>DEFERRED</strong> (never FAIL), and the reviewer accepts
          manual responsibility for them at sign time. Full rule editing is a
          later phase; this panel is read-only.
        </p>
      </div>
    </div>
  );
}
