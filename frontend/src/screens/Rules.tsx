import { useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError, getRules, saveRules } from "../lib/api";
import type { RulesConfig } from "../lib/types";

// Maps are edited as ordered [key, value] rows (so a half-typed REF key doesn't collapse
// the object), then serialized back to a Record on save.
type Entry = { key: string; value: string };

function toEntries(map: Record<string, string> | undefined): Entry[] {
  return Object.entries(map || {}).map(([key, value]) => ({ key, value }));
}

function toMap(entries: Entry[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const { key, value } of entries) {
    const k = key.trim();
    if (k) out[k] = value;
  }
  return out;
}

export function Rules() {
  const [rules, setRules] = useState<RulesConfig | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Per-section editable state.
  const [version, setVersion] = useState("");
  const [gtinOn, setGtinOn] = useState(false);
  const [ai240, setAi240] = useState<"optional" | "required">("optional");
  const [gtinRows, setGtinRows] = useState<Entry[]>([]);
  const [descOn, setDescOn] = useState(false);
  const [matchMode, setMatchMode] = useState<"exact" | "normalized" | "contains">(
    "normalized",
  );
  const [descRows, setDescRows] = useState<Entry[]>([]);
  const [ifuOn, setIfuOn] = useState(false);
  const [ifuRequired, setIfuRequired] = useState(true);
  const [staticOn, setStaticOn] = useState(false);
  const [familyRows, setFamilyRows] = useState<Entry[]>([]); // ref_to_family
  const [familiesJson, setFamiliesJson] = useState("{}");

  const [reviewer, setReviewer] = useState("");
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<{ ok: boolean; msg: string } | null>(null);

  function hydrate(r: RulesConfig) {
    setRules(r);
    setVersion(r.rules_version || "");
    setGtinOn(!!r.gtin?.configured);
    setAi240(r.gtin?.ai240_hyphen === "required" ? "required" : "optional");
    setGtinRows(toEntries(r.gtin?.map));
    setDescOn(!!r.descriptions?.configured);
    setMatchMode(r.descriptions?.match_mode || "normalized");
    setDescRows(toEntries(r.descriptions?.map));
    setIfuOn(!!r.ifu?.configured);
    setIfuRequired(r.ifu?.required_on_label ?? true);
    setStaticOn(!!r.static_content?.configured);
    setFamilyRows(toEntries(r.static_content?.ref_to_family));
    setFamiliesJson(
      JSON.stringify(r.static_content?.families || {}, null, 2),
    );
  }

  useEffect(() => {
    getRules()
      .then(hydrate)
      .catch(() => setLoadError("Could not load the rule set."));
  }, []);

  const configuredVersion = useMemo(() => {
    // A small nudge: stamp today's date when the user activates a check but the version still
    // says "unconfigured", so the recorded rules_version reflects that it's now configured.
    if (!version.includes("unconfigured")) return version;
    if (gtinOn || descOn || ifuOn || staticOn) {
      const today = new Date().toISOString().slice(0, 10);
      return `${today}.configured`;
    }
    return version;
  }, [version, gtinOn, descOn, ifuOn, staticOn]);

  async function handleSave() {
    setSaving(true);
    setStatus(null);

    let families: Record<string, unknown>;
    try {
      families = JSON.parse(familiesJson || "{}");
      if (typeof families !== "object" || Array.isArray(families)) {
        throw new Error("must be an object");
      }
    } catch (e) {
      setSaving(false);
      setStatus({
        ok: false,
        msg: `Static-content "families" is not valid JSON (${(e as Error).message}).`,
      });
      return;
    }

    const payload: RulesConfig = {
      rules_version: configuredVersion,
      gtin: { configured: gtinOn, ai240_hyphen: ai240, map: toMap(gtinRows) },
      descriptions: {
        configured: descOn,
        match_mode: matchMode,
        map: toMap(descRows),
      },
      ifu: { configured: ifuOn, required_on_label: ifuRequired },
      static_content: {
        configured: staticOn,
        families: families as Record<string, unknown>,
        ref_to_family: toMap(familyRows),
      },
    };

    try {
      const saved = await saveRules(payload, reviewer.trim() || undefined);
      hydrate(saved);
      setStatus({ ok: true, msg: `Saved. Active rules version: ${saved.rules_version}.` });
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Save failed.";
      setStatus({ ok: false, msg });
    } finally {
      setSaving(false);
    }
  }

  if (loadError) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8">
        <h1 className="mb-4 text-xl font-bold text-gray-900">Rules</h1>
        <p className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-700">
          {loadError}
        </p>
      </div>
    );
  }

  if (!rules) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8 text-sm text-gray-500">
        Loading rules…
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="mb-1 text-xl font-bold text-gray-900">Rules</h1>
      <p className="mb-6 text-sm text-gray-600">
        Configure the data-driven checks. While a section is{" "}
        <strong>off</strong>, its check returns <strong>DEFERRED</strong> (never
        FAIL) and the reviewer carries it manually. Turn a section on and supply
        the values to make the check active.
      </p>

      <label className="mb-6 block">
        <span className="text-sm font-medium text-gray-700">Rules version</span>
        <input
          className="mt-1 w-full rounded border border-gray-300 px-3 py-2 font-mono text-sm"
          value={version}
          onChange={(e) => setVersion(e.target.value)}
        />
      </label>

      {/* GTIN — Check C, AI(01) */}
      <Section
        title="GTIN match — Check C, AI(01)"
        source="Source: MXO-PP00006"
        on={gtinOn}
        onToggle={setGtinOn}
      >
        <label className="mb-3 block text-sm">
          <span className="font-medium text-gray-700">AI(240) hyphen policy</span>
          <select
            className="ml-2 rounded border border-gray-300 px-2 py-1 text-sm"
            value={ai240}
            onChange={(e) => setAi240(e.target.value as "optional" | "required")}
          >
            <option value="optional">optional (hyphen-only diff PASSes)</option>
            <option value="required">required (hyphen-only diff FLAGs)</option>
          </select>
        </label>
        <MapEditor
          rows={gtinRows}
          setRows={setGtinRows}
          keyLabel="REF"
          valueLabel="GTIN-14"
          keyPlaceholder="MTUUX400-K"
          valuePlaceholder="10881176701838"
        />
      </Section>

      {/* Descriptions — Check D */}
      <Section
        title="Description normalization — Check D"
        source="Source: MXO-PP00001"
        on={descOn}
        onToggle={setDescOn}
      >
        <label className="mb-3 block text-sm">
          <span className="font-medium text-gray-700">Match mode</span>
          <select
            className="ml-2 rounded border border-gray-300 px-2 py-1 text-sm"
            value={matchMode}
            onChange={(e) =>
              setMatchMode(
                e.target.value as "exact" | "normalized" | "contains",
              )
            }
          >
            <option value="normalized">normalized (ignore case/punctuation)</option>
            <option value="exact">exact</option>
            <option value="contains">contains</option>
          </select>
        </label>
        <MapEditor
          rows={descRows}
          setRows={setDescRows}
          keyLabel="REF"
          valueLabel="Canonical description"
          keyPlaceholder="MTUUX400-K"
          valuePlaceholder="TIBIAL BASE PLATE / SIZE 4"
        />
      </Section>

      {/* IFU — Check E */}
      <Section
        title="IFU linkage — Check E"
        source="Source: MXO-PP00001 + sterile CoC"
        on={ifuOn}
        onToggle={setIfuOn}
      >
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={ifuRequired}
            onChange={(e) => setIfuRequired(e.target.checked)}
          />
          The IFU reference must be printed on the label
        </label>
      </Section>

      {/* Static content — Check F */}
      <Section
        title="Static / template content — Check F"
        source="Source: MXO-PP00001"
        on={staticOn}
        onToggle={setStaticOn}
      >
        <p className="mb-2 text-sm font-medium text-gray-700">
          REF → product family
        </p>
        <MapEditor
          rows={familyRows}
          setRows={setFamilyRows}
          keyLabel="REF"
          valueLabel="Family"
          keyPlaceholder="MTUUX400-K"
          valuePlaceholder="FREEDOM_TKS"
        />
        <p className="mb-1 mt-4 text-sm font-medium text-gray-700">
          Per-family static content (advanced — JSON)
        </p>
        <p className="mb-2 text-xs text-gray-500">
          CE notified body, manufacturer / EC-rep addresses, required symbols,
          label revision — keyed by family name.
        </p>
        <textarea
          className="h-48 w-full rounded border border-gray-300 p-2 font-mono text-xs"
          value={familiesJson}
          onChange={(e) => setFamiliesJson(e.target.value)}
          spellCheck={false}
        />
      </Section>

      {/* Save bar */}
      <div className="sticky bottom-0 mt-6 flex items-center gap-3 border-t border-gray-200 bg-white py-4">
        <input
          className="w-48 rounded border border-gray-300 px-3 py-2 text-sm"
          placeholder="Your name (for the audit log)"
          value={reviewer}
          onChange={(e) => setReviewer(e.target.value)}
        />
        <button
          className="rounded bg-gray-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? "Saving…" : "Save rules"}
        </button>
        {status && (
          <span
            className={`text-sm ${status.ok ? "text-green-700" : "text-red-700"}`}
          >
            {status.msg}
          </span>
        )}
      </div>
    </div>
  );
}

// --- presentational helpers -------------------------------------------------

function Section({
  title,
  source,
  on,
  onToggle,
  children,
}: {
  title: string;
  source: string;
  on: boolean;
  onToggle: (v: boolean) => void;
  children: ReactNode;
}) {
  return (
    <section className="mb-5 rounded-lg border border-gray-300 bg-white p-5">
      <div className="mb-3 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-gray-900">{title}</h2>
          <p className="text-xs text-gray-500">{source}</p>
        </div>
        <label className="flex shrink-0 items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={on}
            onChange={(e) => onToggle(e.target.checked)}
          />
          <span className={on ? "font-medium text-green-700" : "text-gray-500"}>
            {on ? "Active" : "Deferred"}
          </span>
        </label>
      </div>
      <div className={on ? "" : "pointer-events-none opacity-50"}>{children}</div>
    </section>
  );
}

function MapEditor({
  rows,
  setRows,
  keyLabel,
  valueLabel,
  keyPlaceholder,
  valuePlaceholder,
}: {
  rows: Entry[];
  setRows: (r: Entry[]) => void;
  keyLabel: string;
  valueLabel: string;
  keyPlaceholder?: string;
  valuePlaceholder?: string;
}) {
  function update(i: number, patch: Partial<Entry>) {
    setRows(rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }
  return (
    <div>
      <div className="mb-1 grid grid-cols-[1fr,2fr,auto] gap-2 text-xs font-medium text-gray-500">
        <span>{keyLabel}</span>
        <span>{valueLabel}</span>
        <span />
      </div>
      {rows.length === 0 && (
        <p className="mb-2 text-xs italic text-gray-400">No entries yet.</p>
      )}
      {rows.map((row, i) => (
        <div key={i} className="mb-2 grid grid-cols-[1fr,2fr,auto] gap-2">
          <input
            className="rounded border border-gray-300 px-2 py-1 font-mono text-sm"
            value={row.key}
            placeholder={keyPlaceholder}
            onChange={(e) => update(i, { key: e.target.value })}
          />
          <input
            className="rounded border border-gray-300 px-2 py-1 text-sm"
            value={row.value}
            placeholder={valuePlaceholder}
            onChange={(e) => update(i, { value: e.target.value })}
          />
          <button
            className="rounded px-2 text-sm text-red-600 hover:bg-red-50"
            onClick={() => setRows(rows.filter((_, idx) => idx !== i))}
            aria-label="Remove row"
          >
            ✕
          </button>
        </div>
      ))}
      <button
        className="mt-1 rounded border border-gray-300 px-3 py-1 text-sm text-gray-700 hover:bg-gray-50"
        onClick={() => setRows([...rows, { key: "", value: "" }])}
      >
        + Add row
      </button>
    </div>
  );
}
