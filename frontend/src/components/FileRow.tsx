import { useRef, useState } from "react";
import { DOC_LABELS, UPLOAD_TESTID, type DocField } from "../lib/types";

const ACCEPTED = /\.(pdf|png|jpe?g|tiff?|webp)$/i;

export function isAcceptable(file: File): boolean {
  return (
    file.type === "application/pdf" ||
    file.type.startsWith("image/") ||
    ACCEPTED.test(file.name)
  );
}

// A drag-and-drop (or click-to-choose) row for a single document slot. Shared by the live
// review and the training screens.
export function FileRow({
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
  const [dragOver, setDragOver] = useState(false);
  const [rejected, setRejected] = useState(false);
  const filled = !!file;

  function take(list: FileList | null | undefined) {
    const f = list?.[0];
    if (!f) return;
    if (!isAcceptable(f)) {
      setRejected(true);
      return;
    }
    setRejected(false);
    onPick(field, f);
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={(e) => {
        e.preventDefault();
        setDragOver(false);
      }}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        take(e.dataTransfer.files);
      }}
      onClick={() => inputRef.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
      }}
      className={`group flex cursor-pointer items-center gap-3 rounded-lg border-2 border-dashed px-3 py-3 transition-colors ${
        dragOver
          ? "border-gray-900 bg-gray-100"
          : filled
            ? "border-solid border-green-300 bg-green-50/40 hover:bg-green-50"
            : rejected
              ? "border-red-300 bg-red-50"
              : "border-gray-300 bg-white hover:border-gray-400 hover:bg-gray-50"
      }`}
    >
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
        {filled ? (
          <div className="truncate text-xs text-gray-500">{file!.name}</div>
        ) : rejected ? (
          <div className="text-xs text-red-600">
            Unsupported file — use a PDF or image.
          </div>
        ) : (
          <div className="text-xs text-gray-400">
            Drag a file here, or click to choose.
          </div>
        )}
      </div>
      <input
        ref={inputRef}
        data-testid={UPLOAD_TESTID[field]}
        type="file"
        accept="application/pdf,image/*"
        className="hidden"
        onChange={(e) => {
          take(e.target.files);
          e.target.value = "";
        }}
      />
      {filled ? (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onClear(field);
          }}
          className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-600 hover:bg-gray-100"
        >
          Remove
        </button>
      ) : (
        <span className="rounded border border-gray-400 px-3 py-1 text-sm font-medium text-gray-700 group-hover:bg-gray-100">
          Choose
        </span>
      )}
    </div>
  );
}
