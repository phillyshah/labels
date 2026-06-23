// Shared types mirroring the backend API contract (docs/07-api-spec.md).

export type Role = "reviewer" | "admin";

export interface LoginResponse {
  token: string;
  role: Role;
}

export type Verdict = "APPROVE" | "APPROVE_WITH_FLAGS" | "REJECT";
export type CheckResult = "PASS" | "FAIL" | "FLAG" | "DEFERRED";

export interface SubResult {
  ai?: string;
  item?: string;
  result: string;
  reason?: string;
}

export interface Check {
  check_code: string; // "A".."G"
  check_name: string;
  result: CheckResult;
  reason: string;
  evidence: Record<string, unknown>;
  sub_results?: SubResult[];
}

export interface Identity {
  ref: string | null;
  lot: string | null;
  sterile_lot: string | null;
  description_label: string | null;
  qty_released: string | null;
  mfg_date: string | null;
  exp_date: string | null;
}

export interface Barcode {
  decoded: boolean;
  symbology: string | null;
  ais: Record<string, string>;
}

export interface SubmissionResult {
  submission_id: string;
  verdict: Verdict;
  rules_version: string;
  processor_ms: number;
  identity: Identity;
  barcode: Barcode;
  checks: Check[];
}

export interface SubmissionListItem {
  id: string;
  created_at: string;
  status: string;
  verdict: Verdict | null;
  ref: string | null;
  lot: string | null;
  sterile_lot: string | null;
}

// 422 error body for a rejected upload.
export interface SubmissionError {
  error: string;
  detail: string;
  submission_id?: string;
}

export interface AcknowledgedFlag {
  item: string;
  note: string;
}

export type SignDecision = "RELEASED" | "REJECTED";

export interface SignRequest {
  decision: SignDecision;
  signer_name: string;
  acknowledged_flags: AcknowledgedFlag[];
}

export interface Approval {
  id: string;
  submission_id: string;
  decision: SignDecision;
  signed_by_name: string;
  signed_at: string;
  acknowledged_flags?: AcknowledgedFlag[];
}

export interface SignResponse {
  approval: Approval;
  bundle_available: boolean;
}

export interface HealthResponse {
  status: string;
  capabilities: Record<string, unknown>;
  rules_version: string;
}

// The upload form's six document slots.
export const REQUIRED_DOCS = [
  "label_form",
  "batch_coc",
  "sterile_coc",
  "sterile_lot_record",
] as const;

export const OPTIONAL_DOCS = [
  "doc_release_verification",
  "sterile_product_release_verification",
] as const;

export type DocField =
  | (typeof REQUIRED_DOCS)[number]
  | (typeof OPTIONAL_DOCS)[number];

// Stable data-testid for each upload input (consumed by the Playwright e2e suite).
export const UPLOAD_TESTID: Record<DocField, string> = {
  label_form: "upload-label",
  batch_coc: "upload-batch-coc",
  sterile_coc: "upload-sterile-coc",
  sterile_lot_record: "upload-sterile-lot-record",
  doc_release_verification: "upload-doc-release-verification",
  sterile_product_release_verification: "upload-sterile-product-release-verification",
};

export const DOC_LABELS: Record<DocField, string> = {
  label_form: "Label form (Reference Label 1st Copy)",
  batch_coc: "Batch CoC",
  sterile_coc: "Sterile Lot CoC",
  sterile_lot_record: "Sterile Lot Record",
  doc_release_verification: "Documentation Release Verification (optional)",
  sterile_product_release_verification:
    "Sterile Product Release Verification (optional)",
};
