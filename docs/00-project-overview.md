# 00 — Project Overview

## The problem

Maxx Orthopedics receives finished, labeled orthopedic implants from contract manufacturer
**Meril Healthcare**. Before those labels are approved for use, a Maxx Quality representative
must manually verify that the printed label content is correct against a chain of supporting
documents (the work instruction governing this is **WI052 R01, §3.0**). Today this is a manual,
paper-based comparison using the **WI052-F1** form. It is slow, error-prone, and the reviewer
has to mentally cross-reference four separate documents.

## The goal

A form-driven web application where a reviewer:

1. Uploads the documents for a batch (label form + batch CoC + sterile CoC + sterile lot record).
2. Clicks **Go**.
3. Receives a **PASS / FAIL / FLAG** scorecard within seconds, with every value traced to its
   source document.
4. Reviews any flags, then applies a digital signature to release — or generates a structured
   discrepancy report to send back to Meril if the label fails.

## Scope of this build

**In scope:** the Meril label path only (WI052 §3.0). The other two paths in WI052 (ACI §4.0
and Maxx-printed §5.0) are explicitly **out of scope** for this phase but the architecture
should not make them impossible to add later.

**In scope deliverables:**
- Form-driven web UI (upload, run, review, sign).
- A document-processing service that extracts fields, decodes the barcode, and runs the checks.
- A checks engine implementing the rules in `docs/05-checks-specification.md`.
- Supabase backend (DB, storage, auth).
- Generated approval record + evidence pack + immutable audit log.
- Deployment behind Traefik on a 90ten.life subdomain on the Hostinger VPS.

**Out of scope (for now):**
- ACI and Maxx-printed label paths.
- Automated outbound email to Meril (the app generates the discrepancy report; a human sends it).
- Integration into a wider QMS (the app is standalone for this phase).

## The three verdict states

Every run resolves to exactly one of:

| Verdict | Meaning | UI behavior |
|---|---|---|
| `APPROVE` | All data checks pass, zero flags. | Green banner. "Sign & Release" enabled. |
| `APPROVE_WITH_FLAGS` | All data checks pass, but ≥1 procedural anomaly exists. | Amber banner. Reviewer must acknowledge each flag before "Sign & Release" enables. |
| `REJECT` | ≥1 data check failed. | Red banner. "Sign & Release" disabled. "Generate Discrepancy Report" enabled. |

A check can also be `DEFERRED` (a rule that depends on MXO-PP00001 / MXO-PP00006, which are
not yet supplied). A `DEFERRED` check never blocks approval but is shown prominently so the
reviewer knows it was not machine-verified and remains their manual responsibility.

## Why a human still signs

This is a regulated quality record. The system is a **decision-support tool**, not an
autonomous approver. It does the cross-referencing a human would do, faster and without
transcription error, but the final "Maxx Approval" signature (WI052 §3.7) is always a
deliberate human act recorded against a named, authenticated reviewer.
