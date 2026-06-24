import { useEffect, useState } from "react";
import {
  OPTIONAL_DOCS,
  REQUIRED_DOCS,
  type CheckResult,
  type DocField,
  type FeedbackItem,
  type Rating,
  type SubmissionError,
  type SubmissionResult,
  type SuggestResponse,
  type TrainingMetrics,
  type Verdict,
} from "../lib/types";
import {
  ApiError,
  createTrainingSubmission,
  submitFeedback,
  suggestRuleChanges,
  trainingMetrics,
} from "../lib/api";
import { FileRow } from "../components/FileRow";

type FileMap = Partial<Record<DocField, File>>;
const ALL_DOCS: DocField[] = [...REQUIRED_DOCS, ...OPTIONAL_DOCS];
const VERDICTS: Verdict[] = ["APPROVE", "APPROVE_WITH_FLAGS", "REJECT"];
const CHECK_RESULTS: CheckResult[] = ["PASS", "FAIL", "FLAG", "DEFERRED"];

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

  // ground-truth mode: provide expected results and auto-score against them
  const [expectedMode, setExpectedMode] = useState(false);
  const [expectedChecks, setExpectedChecks] = useState<Record<string, string>>({});

  // AI rule suggestions
  const [suggest, setSuggest] = useState<SuggestResponse | null>(null);
  const [suggesting, setSuggesting] = useState(false);

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
        setExpectedChecks({});
        setExpectedMode(false);
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

  // Auto-score the tool's output against expected results the reviewer supplied.
  function autoScore() {
    if (!result) return;
    const r: Record<string, Rating> = { ...ratings };
    for (const chk of result.checks) {
      const exp = expectedChecks[chk.check_code];
      if (exp) r[chk.check_code] = exp === chk.result ? "correct" : "wrong";
    }
    if (expectedVerdict)
      r["verdict"] = expectedVerdict === result.verdict ? "correct" : "wrong";
    setRatings(r);
  }

  async function save() {
    if (!result || saving) return;
    const items: FeedbackItem[] = [];
    for (const chk of result.checks) {
      const rt = ratings[chk.check_code];
      if (rt)
        items.push({
          target: chk.check_code,
          rating: rt,
          expected: expectedChecks[chk.check_code] || null,
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

  async function runSuggest() {
    if (suggesting) return;
    setSuggesting(true);
    try {
      setSuggest(await suggestRuleChanges());
    } catch (e) {
      setSuggest({
        available: false,
        suggestions: [],
        message: e instanceof ApiError ? e.message : "could not get suggestions",
      });
    } finally {
      setSuggesting(false);
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

      <div className="mb-6 rounded-lg border border-gray-300 bg-white p-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wide text-gray-500">
              AI rule suggestions
            </h2>
            <p className="mt-1 text-xs text-gray-500">
              Drafts reviewable rule/heuristic changes from where you disagreed with
              the tool. Suggestions only — nothing is applied automatically.
            </p>
          </div>
          <button
            onClick={runSuggest}
            disabled={suggesting}
            className="shrink-0 rounded border border-gray-400 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-50"
          >
            {suggesting ? "Thinking…" : "Suggest improvements"}
          </button>
        </div>
        {suggest && (
          <div className="mt-4">
            {suggest.message && (
              <p className="text-xs text-gray-600">{suggest.message}</p>
            )}
            <div className="mt-2 space-y-2">
              {suggest.suggestions.map((s, i) => (
                <div key={i} className="rounded border border-gray-200 bg-gray-50 p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-gray-800">
                      {s.title}
                    </span>
                    {s.confidence && (
                      <span className="text-[10px] uppercase tracking-wide text-gray-400">
                        {s.confidence} confidence
                      </span>
                    )}
                  </div>
                  {s.target && (
                    <div className="mt-0.5 text-xs text-gray-500">{s.target}</div>
                  )}
                  {s.rationale && (
                    <p className="mt-1 text-xs text-gray-600">{s.rationale}</p>
                  )}
                  {s.proposed_change && (
                    <pre className="mt-2 overflow-x-auto rounded bg-gray-900 p-2 text-[11px] text-gray-100">
                      {s.proposed_change}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

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
              {(expectedMode || ratings["verdict"] === "wrong") && (
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

          <div className="mb-3 flex items-center justify-between rounded bg-gray-50 px-3 py-2">
            <label className="flex items-center gap-2 text-xs font-medium text-gray-700">
              <input
                type="checkbox"
                checked={expectedMode}
                onChange={(e) => setExpectedMode(e.target.checked)}
              />
              I have the expected results (auto-score)
            </label>
            {expectedMode && (
              <button
                onClick={autoScore}
                className="rounded border border-gray-400 px-3 py-1 text-xs font-semibold text-gray-700 hover:bg-gray-100"
              >
                Auto-score from expected
              </button>
            )}
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
                  <div className="flex shrink-0 items-center gap-2">
                    {expectedMode && (
                      <select
                        value={expectedChecks[chk.check_code] ?? ""}
                        onChange={(e) =>
                          setExpectedChecks((p) => ({
                            ...p,
                            [chk.check_code]: e.target.value,
                          }))
                        }
                        className="rounded border border-gray-300 px-1.5 py-1 text-xs"
                        title="expected result"
                      >
                        <option value="">Expected…</option>
                        {CHECK_RESULTS.map((r) => (
                          <option key={r} value={r}>
                            {r}
                          </option>
                        ))}
                      </select>
                    )}
                    <RatingButtons
                      value={ratings[chk.check_code]}
                      onChange={(r) =>
                        setRatings((p) => ({ ...p, [chk.check_code]: r }))
                      }
                    />
                  </div>
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
