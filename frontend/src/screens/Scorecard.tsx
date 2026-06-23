import { useEffect, useMemo, useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import type {
  AcknowledgedFlag,
  SignResponse,
  SubmissionResult,
  Verdict,
} from "../lib/types";
import {
  ApiError,
  fetchBundleUrl,
  getSubmission,
  sign as apiSign,
} from "../lib/api";
import { collectDeferred, collectFlags } from "../lib/scorecard";
import { ScorecardTable } from "../components/ScorecardTable";
import { SourceOfTruth } from "../components/SourceOfTruth";

const BANNER: Record<
  Verdict,
  { icon: string; label: string; cls: string }
> = {
  APPROVE: {
    icon: "✔",
    label: "APPROVE",
    cls: "bg-green-600 text-white",
  },
  APPROVE_WITH_FLAGS: {
    icon: "▲",
    label: "APPROVE WITH FLAGS",
    cls: "bg-amber-500 text-white",
  },
  REJECT: { icon: "✖", label: "REJECT", cls: "bg-red-600 text-white" },
};

function VerdictBanner({ result }: { result: SubmissionResult }) {
  const b = BANNER[result.verdict];
  const { ref, lot, sterile_lot } = result.identity;
  return (
    <div data-testid="verdict-banner" className={`rounded-lg px-5 py-4 ${b.cls}`}>
      <div className="flex items-center gap-3 text-2xl font-bold">
        <span aria-hidden>{b.icon}</span>
        <span>{b.label}</span>
      </div>
      <div data-testid="identity-summary" className="mt-1 text-sm font-medium opacity-95">
        REF {ref ?? "—"} · LOT {lot ?? "—"} · Sterile lot {sterile_lot ?? "—"}
      </div>
    </div>
  );
}

export function Scorecard() {
  const { id = "" } = useParams();
  const location = useLocation();
  const preloaded = (location.state as { result?: SubmissionResult } | null)
    ?.result;

  const [result, setResult] = useState<SubmissionResult | null>(
    preloaded && preloaded.submission_id === id ? preloaded : null,
  );
  const [loading, setLoading] = useState(!result);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (result && result.submission_id === id) return;
    let active = true;
    setLoading(true);
    setLoadError(null);
    getSubmission(id)
      .then((r) => active && setResult(r))
      .catch((e) => {
        if (!active) return;
        setLoadError(
          e instanceof ApiError ? e.message : "could not load submission",
        );
      })
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16 text-center text-gray-600">
        Loading submission…
      </div>
    );
  }
  if (loadError || !result) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-12">
        <div className="rounded-lg border border-red-300 bg-red-50 p-5 text-sm text-red-900">
          {loadError ?? "Submission not found."}
        </div>
      </div>
    );
  }

  return <ScorecardBody result={result} />;
}

function ScorecardBody({ result }: { result: SubmissionResult }) {
  const flags = useMemo(() => collectFlags(result), [result]);
  const deferred = useMemo(() => collectDeferred(result), [result]);

  // Acknowledgement state keyed by flag id.
  const [acked, setAcked] = useState<Record<string, boolean>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});

  const [signerName, setSignerName] = useState("");
  const [signing, setSigning] = useState(false);
  const [signError, setSignError] = useState<string | null>(null);
  const [signed, setSigned] = useState<SignResponse | null>(null);
  const [bundleUrl, setBundleUrl] = useState<string | null>(null);
  const [bundleError, setBundleError] = useState<string | null>(null);

  const allAcked = flags.every((f) => acked[f.id]);
  const isReject = result.verdict === "REJECT";
  const canSign =
    !signing && signerName.trim().length > 0 && (isReject || allAcked);

  async function doSign(decision: "RELEASED" | "REJECTED") {
    if (signing) return;
    setSignError(null);
    setSigning(true);
    const acknowledged_flags: AcknowledgedFlag[] = flags.map((f) => ({
      item: f.label,
      note: notes[f.id] ?? "",
    }));
    try {
      const res = await apiSign(result.submission_id, {
        decision,
        signer_name: signerName.trim(),
        acknowledged_flags: decision === "RELEASED" ? acknowledged_flags : [],
      });
      setSigned(res);
      if (res.bundle_available) {
        fetchBundleUrl(result.submission_id)
          .then(setBundleUrl)
          .catch(() => setBundleError("bundle not available yet"));
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setSignError("This submission has already been signed (immutable).");
      } else {
        setSignError(
          e instanceof ApiError ? e.message : "could not sign — try again",
        );
      }
    } finally {
      setSigning(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-4 py-8">
      <VerdictBanner result={result} />

      <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-gray-500">
        <span>Submission {result.submission_id}</span>
        <span>Rules {result.rules_version}</span>
        <span>Processed in {result.processor_ms} ms</span>
      </div>

      {result.source_of_truth && (
        <SourceOfTruth rows={result.source_of_truth} />
      )}

      <ScorecardTable checks={result.checks} />

      {/* Flags to acknowledge */}
      <section className="rounded-lg border border-amber-300 bg-amber-50 p-5">
        <h2 className="text-base font-bold text-amber-900">
          Flags to acknowledge
        </h2>
        {flags.length === 0 ? (
          <p className="mt-1 text-sm text-amber-800">No flags raised.</p>
        ) : (
          <ul className="mt-3 space-y-3">
            {flags.map((f) => (
              <li
                key={f.id}
                className="rounded border border-amber-200 bg-white p-3"
              >
                <label className="flex items-start gap-2">
                  <input
                    type="checkbox"
                    data-testid={`flag-ack-${f.id}`}
                    className="mt-1 h-4 w-4"
                    checked={!!acked[f.id]}
                    onChange={(e) =>
                      setAcked((p) => ({ ...p, [f.id]: e.target.checked }))
                    }
                  />
                  <span className="text-sm">
                    <span className="font-mono font-semibold text-gray-800">
                      {f.label}
                    </span>
                    {f.reason && (
                      <span className="text-gray-600"> — {f.reason}</span>
                    )}
                  </span>
                </label>
                <input
                  type="text"
                  placeholder="Note (optional)"
                  value={notes[f.id] ?? ""}
                  onChange={(e) =>
                    setNotes((p) => ({ ...p, [f.id]: e.target.value }))
                  }
                  className="mt-2 w-full rounded border border-gray-300 px-2 py-1 text-sm focus:border-gray-900 focus:outline-none"
                />
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Not machine-verified (DEFERRED) */}
      <section
        data-testid="deferred-panel"
        className="rounded-lg border border-gray-300 bg-gray-50 p-5"
      >
        <h2 className="text-base font-bold text-gray-800">
          Not machine-verified (DEFERRED)
        </h2>
        <p className="mt-1 text-sm text-gray-600">
          These were not checked automatically. Signing implies you accept
          manual responsibility for verifying them.
        </p>
        {deferred.length === 0 ? (
          <p className="mt-2 text-sm text-gray-600">Nothing deferred.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {deferred.map((d) => (
              <li
                key={d.id}
                className="rounded border border-gray-200 bg-white p-3 text-sm"
              >
                <span className="font-mono font-semibold text-gray-800">
                  {d.label}
                </span>
                {d.reason && (
                  <span className="text-gray-600"> — {d.reason}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Sign actions / success */}
      {signed ? (
        <section
          data-testid="release-confirmation"
          className="rounded-lg border border-green-400 bg-green-50 p-5"
        >
          <h2 className="text-base font-bold text-green-900">
            {signed.approval.decision === "RELEASED"
              ? "Released"
              : "Discrepancy report generated"}
          </h2>
          <p className="mt-1 text-sm text-green-900">
            Signed by {signed.approval.signed_by_name} on{" "}
            {new Date(signed.approval.signed_at).toLocaleString()}.
          </p>
          {signed.bundle_available ? (
            bundleUrl ? (
              <a
                href={bundleUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-3 inline-block rounded bg-gray-900 px-4 py-2 text-sm font-semibold text-white hover:bg-gray-800"
              >
                Open approval bundle (PDF)
              </a>
            ) : (
              <p className="mt-3 text-sm text-green-800">
                {bundleError ?? "Preparing bundle…"}
              </p>
            )
          ) : (
            <p className="mt-3 text-sm text-green-800">
              No bundle was generated.
            </p>
          )}
        </section>
      ) : (
        <section className="rounded-lg border border-gray-300 bg-white p-5">
          <label
            htmlFor="signer"
            className="mb-1 block text-sm font-medium text-gray-700"
          >
            Reviewer name (signer of record)
          </label>
          <input
            id="signer"
            type="text"
            value={signerName}
            onChange={(e) => setSignerName(e.target.value)}
            placeholder="Your full name"
            className="mb-4 w-full max-w-sm rounded border border-gray-300 px-3 py-2 text-sm focus:border-gray-900 focus:outline-none"
          />

          {signError && (
            <p className="mb-3 text-sm font-medium text-red-700" role="alert">
              {signError}
            </p>
          )}

          {isReject ? (
            <button
              onClick={() => doSign("REJECTED")}
              disabled={!canSign}
              className="rounded bg-red-700 px-5 py-2 text-sm font-bold text-white hover:bg-red-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {signing ? "Generating…" : "Generate Discrepancy Report"}
            </button>
          ) : (
            <>
              <button
                onClick={() => doSign("RELEASED")}
                disabled={!canSign}
                className="rounded bg-green-700 px-5 py-2 text-sm font-bold text-white hover:bg-green-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {signing ? "Signing…" : "Sign & Release"}
              </button>
              {!isReject && flags.length > 0 && !allAcked && (
                <p className="mt-2 text-xs text-amber-700">
                  Acknowledge all flags above to enable Sign &amp; Release.
                </p>
              )}
            </>
          )}
        </section>
      )}
    </div>
  );
}
