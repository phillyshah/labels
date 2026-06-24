import { useEffect, useState } from "react";
import {
  OPTIONAL_DOCS,
  REQUIRED_DOCS,
  type DocField,
  type FeedbackItem,
  type Rating,
  type SubmissionError,
  type SubmissionResult,
  type TrainingMetrics,
  type Verdict,
} from "../lib/types";
import {
  ApiError,
  createTrainingSubmission,
  submitFeedback,
  trainingMetrics,
} from "../lib/api";
import { FileRow } from "../components/FileRow";

type FileMap = Partial<Record<DocField, File>>;
const ALL_DOCS: DocField[] = [...REQUIRED_DOCS, ...OPTIONAL_DOCS];
const VERDICTS: Verdict[] = ["APPROVE", "APPROVE_WITH_FLAGS", "REJECT"];

const RESULT_COLOR: Record<string, string> = {
  PASS: "text-green-700",
  FAIL: "text-red-700",
  FLAG: "text-amber-700",
  DEFERRED: "text-gray-500",
};

function pct(v: number | null): string {
  return v === null ? "—" : `${Math.round(v * 100)}%`;
}

function RatingButtons({
  value,
  onChange,
}: {
  value: Rating | undefined;
  onChange: (r: Rating) => void;
}) {
  const opts: { r: Rating; label: string; on: string }[] = [
    { r: "correct", label: "Correct", on: "bg-green-600 text-white" },
    { r: "partial", label: "Partial", on: "bg-amber-500 text-white" },
    { r: "wrong", label: "Wrong", on: "bg-red-600 text-white" },
  ];
  return (
    <div className="flex gap-1">
      {opts.map((o) => (
        <button
          key={o.r}
          onClick={() => onChange(o.r)}
          className={`rounded px-2 py-1 text-xs font-semibold ${
            value === o.r
              ? o.on
              : "border border-gray-300 text-gray-600 hover:bg-gray-100"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

// --- accuracy dashboard ------------------------------------------------------

function MetricsPanel({ metrics }: { metrics: TrainingMetrics | null }) {
  if (!metrics) return null;
  const targets = Object.keys(metrics.by_target);
  return (
    <div className="mb-6 rounded-lg border border-gray-300 bg-white p-5">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="text-sm font-bold uppercase tracking-wide text-gray-500">
          Accuracy
        </h2>
        <span className="text-xs text-gray-500">
          {metrics.batches} training batch{metrics.batches === 1 ? "" : "es"} ·{" "}
          {metrics.feedback_count} judgement
          {metrics.feedback_count === 1 ? "" : "s"}
        </span>
      </div>
      <div className="mb-4 flex items-end gap-2">
        <span className="text-4xl font-bold text-gray-900">
          {pct(metrics.overall.accuracy)}
        </span>
        <span className="mb-1 text-xs text-gray-500">
          overall agreement (correct=1, partial=½)
        </span>
      </div>
      {targets.length > 0 && (
        <div className="space-y-1.5">
          {targets.map((t) => {
            const b = metrics.by_target[t];
            const a = b.accuracy ?? 0;
            return (
              <div key={t} className="flex items-center gap-3 text-xs">
                <span className="w-16 shrink-0 font-medium text-gray-700">
                  {t === "verdict" ? "Verdict" : `Check ${t}`}
                </span>
                <div className="h-2 flex-1 overflow-hidden rounded bg-gray-200">
                  <div
                    className={`h-full ${a >= 0.8 ? "bg-green-500" : a >= 0.5 ? "bg-amber-500" : "bg-red-500"}`}
                    style={{ width: `${a * 100}%` }}
                  />
                </div>
                <span className="w-10 shrink-0 text-right text-gray-500">
                  {pct(b.accuracy)}
                </span>
                <span className="w-20 shrink-0 text-right text-gray-400">
                  {b.correct}✓ {b.partial}~ {b.wrong}✗
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// --- main screen -------------------------------------------------------------

export function Training() {
  const [files, setFiles] = useState<FileMap>({});
  const [phase, setPhase] = useState<
    "idle" | "processing" | "review" | "saved" | "error"
  >("idle");
  const [result, setResult] = useState<SubmissionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<TrainingMetrics | null>(null);

  // feedback state
  const [reviewer, setReviewer] = useState("");
  const [ratings, setRatings] = useState<Record<string, Rating>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [expectedVerdict, setExpectedVerdict] = useState<string>("");
  const [saving, setSaving] = useState(false);

  const requiredMet = REQUIRED_DOCS.every((d) => !!files[d]);

  function loadMetrics() {
    trainingMetrics()
      .then(setMetrics)
      .catch(() => {});
  }
  useEffect(loadMetrics, []);

  function pick(field: DocField, file: File) {
    setFiles((p) => ({ ...p, [field]: file }));
  }
  function clear(field: DocField) {
    setFiles((p) => {
      const n = { ...p };
      delete n[field];
      return n;
    });
  }

  async function process() {
    if (!requiredMet || phase === "processing") return;
    setPhase("processing");
    setError(null);
    const payload: Record<string, File> = {};
    for (const d of ALL_DOCS) {
      const f = files[d];
      if (f) payload[d] = f;
    }
    try {
      const res = await createTrainingSubmission(payload);
      if (res.ok) {
        setResult(res.result);
        setRatings({});
        setNotes({});
        setExpectedVerdict("");
        setPhase("review");
      } else {
        const e = res.error as SubmissionError;
        setError(`${e.error === "DOCUMENT_MISMATCH" ? "" : e.error + ": "}${e.detail}`);
        setPhase("error");
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "upload failed — try again");
      setPhase("error");
    }
  }

  async function save() {
    if (!result || saving) return;
    const items: FeedbackItem[] = [];
    for (const chk of result.checks) {
      const r = ratings[chk.check_code];
      if (r)
        items.push({
          target: chk.check_code,
          rating: r,
          note: notes[chk.check_code] || null,
        });
    }
    if (ratings["verdict"]) {
      items.push({
        target: "verdict",
        rating: ratings["verdict"],
        expected: expectedVerdict || null,
        note: notes["verdict"] || null,
      });
    }
    if (items.length === 0) {
      setError("Rate at least one check or the verdict before saving.");
      return;
    }
    setSaving(true);
    try {
      await submitFeedback(result.submission_id, {
        reviewer_name: reviewer.trim() || undefined,
        items,
      });
      setPhase("saved");
      setFiles({});
      setResult(null);
      loadMetrics();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "could not save feedback");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="mb-1 text-xl font-bold text-gray-900">Training</h1>
      <p className="mb-6 text-sm text-gray-600">
        Upload a batch that was already processed by hand, let the tool run it,
        then tell it where it was right or wrong. Your feedback builds a labeled
        corpus that drives rule tuning and tracks accuracy over time.
      </p>

      <MetricsPanel metrics={metrics} />

      {phase === "saved" && (
        <div className="mb-6 rounded-lg border border-green-300 bg-green-50 p-4 text-sm text-green-900">
          Feedback saved. Accuracy updated above — upload another batch to keep
          training.
        </div>
      )}

      {phase !== "review" && (
        <div className="rounded-lg border border-gray-300 bg-white p-5">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
            Required
          </div>
          <div className="space-y-2">
            {REQUIRED_DOCS.map((d) => (
              <FileRow key={d} field={d} file={files[d]} onPick={pick} onClear={clear} />
            ))}
          </div>
          <div className="mb-2 mt-5 text-xs font-semibold uppercase tracking-wide text-gray-500">
            Optional
          </div>
          <div className="space-y-2">
            {OPTIONAL_DOCS.map((d) => (
              <FileRow key={d} field={d} file={files[d]} onPick={pick} onClear={clear} />
            ))}
          </div>
          {error && phase === "error" && (
            <p className="mt-4 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800">
              {error}
            </p>
          )}
          <div className="mt-6 flex items-center justify-between">
            <span className="text-xs text-gray-500">
              {requiredMet
                ? "Ready to process."
                : "Attach all four required documents."}
            </span>
            <button
              onClick={process}
              disabled={!requiredMet || phase === "processing"}
              className="rounded bg-gray-900 px-6 py-2 text-sm font-bold text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {phase === "processing" ? "Processing…" : "Process batch"}
            </button>
          </div>
        </div>
      )}

      {phase === "review" && result && (
        <div className="rounded-lg border border-gray-300 bg-white p-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <div className="text-xs uppercase tracking-wide text-gray-500">
                Tool verdict
              </div>
              <div className="text-lg font-bold text-gray-900">
                {result.verdict}
              </div>
              <div className="text-xs text-gray-500">
                REF {result.identity.ref} · LOT {result.identity.lot}
              </div>
            </div>
            <div className="text-right">
              <div className="mb-1 text-xs font-medium text-gray-600">
                Verdict correct?
              </div>
              <RatingButtons
                value={ratings["verdict"]}
                onChange={(r) => setRatings((p) => ({ ...p, verdict: r }))}
              />
              {ratings["verdict"] === "wrong" && (
                <select
                  value={expectedVerdict}
                  onChange={(e) => setExpectedVerdict(e.target.value)}
                  className="mt-2 rounded border border-gray-300 px-2 py-1 text-xs"
                >
                  <option value="">Expected…</option>
                  {VERDICTS.map((v) => (
                    <option key={v} value={v}>
                      {v}
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>

          <div className="divide-y divide-gray-200 border-y border-gray-200">
            {result.checks.map((chk) => (
              <div key={chk.check_code} className="py-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <span className="text-sm font-semibold text-gray-800">
                      {chk.check_code} — {chk.check_name}
                    </span>{" "}
                    <span
                      className={`text-xs font-bold ${RESULT_COLOR[chk.result] ?? "text-gray-600"}`}
                    >
                      {chk.result}
                    </span>
                    <p className="mt-0.5 text-xs text-gray-500">{chk.reason}</p>
                  </div>
                  <RatingButtons
                    value={ratings[chk.check_code]}
                    onChange={(r) =>
                      setRatings((p) => ({ ...p, [chk.check_code]: r }))
                    }
                  />
                </div>
                {ratings[chk.check_code] &&
                  ratings[chk.check_code] !== "correct" && (
                    <input
                      value={notes[chk.check_code] ?? ""}
                      onChange={(e) =>
                        setNotes((p) => ({
                          ...p,
                          [chk.check_code]: e.target.value,
                        }))
                      }
                      placeholder="What should it have done? (optional)"
                      className="mt-2 w-full rounded border border-gray-300 px-2 py-1 text-xs focus:border-gray-900 focus:outline-none"
                    />
                  )}
              </div>
            ))}
          </div>

          <div className="mt-4">
            <label className="mb-1 block text-xs font-medium text-gray-600">
              Your name (optional)
            </label>
            <input
              value={reviewer}
              onChange={(e) => setReviewer(e.target.value)}
              className="w-56 rounded border border-gray-300 px-2 py-1 text-sm focus:border-gray-900 focus:outline-none"
            />
          </div>

          {error && (
            <p className="mt-3 text-sm text-red-700">{error}</p>
          )}

          <div className="mt-5 flex items-center justify-end gap-2">
            <button
              onClick={() => {
                setPhase("idle");
                setResult(null);
                setError(null);
              }}
              className="rounded border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
            >
              Discard
            </button>
            <button
              onClick={save}
              disabled={saving}
              className="rounded bg-gray-900 px-6 py-2 text-sm font-bold text-white hover:bg-gray-800 disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save feedback"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
