// Renders an arbitrary JSON value (a check's `evidence`) in a readable,
// monospaced block.
export function Json({ value }: { value: unknown }) {
  if (value === null || value === undefined) {
    return <span className="text-gray-500">—</span>;
  }
  return (
    <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded bg-gray-900 p-3 text-xs leading-relaxed text-gray-100">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}
