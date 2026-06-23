import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  DOC_LABELS,
  OPTIONAL_DOCS,
  REQUIRED_DOCS,
  UPLOAD_TESTID,
  type DocField,
  type SubmissionError,
} from "../lib/types";
import { ApiError, createSubmission } from "../lib/api";

type FileMap = Partial<Record<DocField, File>>;

const ALL_DOCS: DocField[] = [...REQUIRED_DOCS, ...OPTIONAL_DOCS];

function FileRow({
  field,
  file,
  onPick,
  onClear,
}: {
  field: DocField;
  file: File | undefined;
  onPick: (field: DocField, file: File) => void;
  onClear: (field: DocField) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const filled = !!file;
  return (
    <div className="flex items-center gap-3 border-b border-gray-200 py-2.5 last:border-b-0">
      <span
        className={`h-3 w-3 shrink-0 rounded-full ${
          filled ? "bg-green-500" : "bg-gray-300"
        }`}
        aria-label={filled ? "file selected" : "no file"}
      />
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium text-gray-800">
          {DOC_LABELS[field]}
        </div>
        {filled && (
          <div className="truncate text-xs text-gray-500">{file!.name}</div>
        )}
      </div>
      <input
        ref={inputRef}
        data-testid={UPLOAD_TESTID[field]}
        type="file"
        accept="application/pdf,image/*"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onPick(field, f);
          e.target.value = "";
        }}
      />
      {filled ? (
        <button
          onClick={() => onClear(field)}
          className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-600 hover:bg-gray-100"
        >
          Remove
        </button>
      ) : null}
      <button
        onClick={() => inputRef.current?.click()}
        className="rounded border border-gray-400 px-3 py-1 text-sm font-medium text-gray-700 hover:bg-gray-100"
      >
        Choose
      </button>
    </div>
  );
}

export function NewReview() {
  const navigate = useNavigate();
  const [files, setFiles] = useState<FileMap>({});
  const [phase, setPhase] = useState<"idle" | "processing" | "error">("idle");
  const [submissionError, setSubmissionError] =
    useState<SubmissionError | null>(null);
  const [fatalError, setFatalError] = useState<string | null>(null);

  const requiredMet = REQUIRED_DOCS.every((d) => !!files[d]);

  function pick(field: DocField, file: File) {
    setFiles((prev) => ({ ...prev, [field]: file }));
  }
  function clear(field: DocField) {
    setFiles((prev) => {
      const next = { ...prev };
      delete next[field];
      return next;
    });
  }

  async function go() {
    if (!requiredMet || phase === "processing") return;
    setPhase("processing");
    setSubmissionError(null);
    setFatalError(null);

    const payload: Record<string, File> = {};
    for (const d of ALL_DOCS) {
      const f = files[d];
      if (f) payload[d] = f;
    }

    try {
      const res = await createSubmission(payload);
      if (res.ok) {
        navigate(`/submissions/${res.result.submission_id}`, {
          state: { result: res.result },
        });
      } else {
        setSubmissionError(res.error);
        setPhase("error");
      }
    } catch (e) {
      const msg =
        e instanceof ApiError ? e.message : "upload failed — please try again";
      setFatalError(msg);
      setPhase("error");
    }
  }

  if (phase === "processing") {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 text-center">
        <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-4 border-gray-300 border-t-gray-900" />
        <h2 className="text-lg font-semibold text-gray-900">Processing</h2>
        <p className="mt-1 text-sm text-gray-600">Usually under 30s.</p>
      </div>
    );
  }

  if (phase === "error") {
    return (
      <div className="mx-auto max-w-2xl px-4 py-12">
        <div
          data-testid="error-message"
          className="rounded-lg border border-red-300 bg-red-50 p-5"
        >
          <h2 className="text-base font-bold text-red-900">
            {submissionError ? "Submission rejected" : "Upload failed"}
          </h2>
          {submissionError ? (
            <div className="mt-2 space-y-1 text-sm text-red-900">
              <p className="font-semibold">{submissionError.error}</p>
              <p>{submissionError.detail}</p>
            </div>
          ) : (
            <p className="mt-2 text-sm text-red-900">{fatalError}</p>
          )}
          <button
            onClick={() => {
              setPhase("idle");
              setSubmissionError(null);
              setFatalError(null);
            }}
            className="mt-4 rounded bg-gray-900 px-3 py-2 text-sm font-semibold text-white hover:bg-gray-800"
          >
            Back to upload
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="mb-1 text-xl font-bold text-gray-900">New Label Review</h1>
      <p className="mb-6 text-sm text-gray-600">
        Attach the batch documents, then click Go. PDFs and label scans
        accepted.
      </p>

      <div className="rounded-lg border border-gray-300 bg-white p-5">
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
          Required
        </div>
        {REQUIRED_DOCS.map((d) => (
          <FileRow
            key={d}
            field={d}
            file={files[d]}
            onPick={pick}
            onClear={clear}
          />
        ))}

        <div className="mb-2 mt-5 text-xs font-semibold uppercase tracking-wide text-gray-500">
          Optional
        </div>
        {OPTIONAL_DOCS.map((d) => (
          <FileRow
            key={d}
            field={d}
            file={files[d]}
            onPick={pick}
            onClear={clear}
          />
        ))}

        <div className="mt-6 flex items-center justify-between">
          <span className="text-xs text-gray-500">
            {requiredMet
              ? "All required documents attached."
              : "Attach all four required documents to continue."}
          </span>
          <button
            onClick={go}
            disabled={!requiredMet}
            className="rounded bg-gray-900 px-6 py-2 text-sm font-bold text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Go
          </button>
        </div>
      </div>
    </div>
  );
}
