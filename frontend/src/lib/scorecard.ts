// Helpers that derive the flag and deferred lists from a result's checks,
// per the frontend spec.

import type { Check, SubmissionResult } from "./types";

export interface FlagItem {
  // Stable identifier used as the `item` in acknowledged_flags and as a key.
  id: string;
  check_code: string;
  // Human label for what is flagged.
  label: string;
  reason: string;
}

export interface DeferredItem {
  id: string;
  check_code: string;
  label: string;
  reason: string;
}

function subLabel(check: Check, ai?: string, item?: string): string {
  const part = item || (ai ? `AI(${ai})` : "");
  return part ? `${check.check_code} · ${part}` : check.check_code;
}

// Every sub_result with result === "FLAG", plus any top-level check with
// result === "FLAG" that has no sub_results.
export function collectFlags(result: SubmissionResult): FlagItem[] {
  const flags: FlagItem[] = [];
  for (const check of result.checks) {
    const subs = check.sub_results ?? [];
    const flaggedSubs = subs.filter((s) => s.result === "FLAG");
    for (const s of flaggedSubs) {
      flags.push({
        id: `${check.check_code}:${s.item ?? s.ai ?? flags.length}`,
        check_code: check.check_code,
        label: subLabel(check, s.ai, s.item),
        reason: s.reason ?? check.reason ?? "",
      });
    }
    if (check.result === "FLAG" && subs.length === 0) {
      flags.push({
        id: `${check.check_code}`,
        check_code: check.check_code,
        label: `${check.check_code} · ${check.check_name}`,
        reason: check.reason ?? "",
      });
    }
  }
  return flags;
}

// Every check and sub-item whose result is DEFERRED.
export function collectDeferred(result: SubmissionResult): DeferredItem[] {
  const out: DeferredItem[] = [];
  for (const check of result.checks) {
    if (check.result === "DEFERRED") {
      out.push({
        id: `${check.check_code}`,
        check_code: check.check_code,
        label: `${check.check_code} · ${check.check_name}`,
        reason: check.reason ?? "",
      });
    }
    for (const s of check.sub_results ?? []) {
      if (s.result === "DEFERRED") {
        out.push({
          id: `${check.check_code}:${s.item ?? s.ai ?? out.length}`,
          check_code: check.check_code,
          label: subLabel(check, s.ai, s.item),
          reason: s.reason ?? "",
        });
      }
    }
  }
  return out;
}
