import { useEffect } from "react";
import type { VersionInfo } from "../lib/types";

// Changelog modal opened from the header "What's New" button. Closes via the X,
// a backdrop click, or Esc — matching the convention used across the projects.
export function WhatsNew({
  open,
  onClose,
  info,
}: {
  open: boolean;
  onClose: () => void;
  info: VersionInfo | null;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-4 pt-16"
    >
      <div className="max-h-[80vh] w-full max-w-lg overflow-y-auto rounded-lg bg-white shadow-xl">
        <div className="sticky top-0 flex items-center justify-between border-b border-gray-200 bg-white px-5 py-3">
          <h2 className="text-base font-bold text-gray-900">What's New</h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
          >
            ✕
          </button>
        </div>
        <div className="space-y-5 px-5 py-4">
          {info ? (
            info.changelog.map((entry) => (
              <div key={entry.version}>
                <div className="flex items-baseline gap-2">
                  <span className="text-sm font-semibold text-gray-900">
                    v{entry.version}
                  </span>
                  <span className="text-xs text-gray-400">{entry.date}</span>
                </div>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-gray-700">
                  {entry.notes.map((n, i) => (
                    <li key={i}>{n}</li>
                  ))}
                </ul>
              </div>
            ))
          ) : (
            <p className="text-sm text-gray-500">Couldn't load changelog.</p>
          )}
        </div>
      </div>
    </div>
  );
}
