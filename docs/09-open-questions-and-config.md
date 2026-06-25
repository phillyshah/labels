# 09 — Open Questions & Configuration (owned by Maxx Quality)

These must be resolved by Maxx, not guessed by the coding team. Build defaults are noted; flag
each for confirmation.

## Decisions blocking full functionality

1. **MXO-PP00001 (Labeling Guidelines) — not yet supplied.** Source of truth for canonical
   descriptions (Check D), IFU print requirements (E), and all static content (F). Until
   supplied, D/E/F return `DEFERRED`. Build against `config/rules.example.yaml`.
   *Default:* deferred. *Needs:* the document, plus confirmation of how strictly descriptions
   must match (`exact` vs `normalized` vs `contains`).

2. **MXO-PP00006 (GTIN Codes) — not yet supplied.** Source of truth for the GTIN inside the
   barcode (Check C, AI 01). Until supplied, AI(01) is `DEFERRED`.
   *Needs:* the REF→GTIN mapping, and the AI(240) hyphen policy (`required` vs `optional`).

3. **Exact subdomain.** Proposed `labelcheck.90ten.life`. *Needs:* confirmation before DNS.

4. **Supabase: cloud vs self-hosted.** Which does 90ten.life already run on the VPS? Affects
   migrations, backups, and the service-role key handling. *Needs:* confirmation.

## Process decisions

5. **Single-batch vs multi-batch runs.** Sterile lot M26-179 has 12 batches, each with its own
   label + batch CoC, sharing the sterile CoC + Sterile Lot Record. *Default (this build):* one
   submission = one batch. *Option:* a "lot mode" that accepts 12 label forms + 12 batch CoCs +
   1 shared sterile CoC + 1 shared Sterile Lot Record and produces 12 scorecards. Confirm
   whether lot mode is wanted now or later.

6. **Does machine barcode-decode satisfy WI052 §3.6?** The processor decodes the 2D code from
   the PDF image. Is that the "scanned & verified" step, or must Quality still scan the physical
   printed label with a handheld scanner? *Default:* the app records that it decoded and matched
   the barcode, but **does not** auto-check the WI052-F1 "Barcode scanned & Verified" box — the
   reviewer affirms that during signing. Confirm whether Maxx wants the app to own that box.

7. **Deviation handling (Check G.2).** When a lot is released under a deviation (e.g. 25.17),
   should the app: (a) flag only — current default; (b) block approval until acknowledged; or
   (c) fetch the deviation record from a deviations log if one is made available? *Default:*
   flag + require acknowledgement on the amber path. *Needs:* whether a deviations data source
   exists to integrate.

8. **Description match strictness.** Tied to #1. The sample shows three legitimate phrasings of
   the same part. Maxx must define what counts as "correct."

## Records & compliance decisions

9. **DHR delivery.** WI052 §3.8 says the approved form becomes part of the DHR. *Default:* the
   app generates the approval bundle PDF and stores it; *Needs:* where/how the DHR ingests it
   (manual download, a watched folder, an API?).

10. **Meril approval email (WI052 §3.8 / §3.9).** *Default (this build):* the app generates the
    approval confirmation / discrepancy report; a human emails Meril. Confirm Maxx does not want
    automated outbound email in this phase.

11. **Retention & e-signature posture.** Confirm whether the digital signature approach
    (authenticated user + timestamp + immutable record) satisfies Maxx's 21 CFR Part 11
    expectations for this record, or whether a stronger e-signature mechanism is required. This
    is a regulatory decision for Maxx Quality, not the coding team.

## Tooling confirmation

12. **VPS document tooling inventory.** The processor reuses existing VPS binaries
    (poppler/tesseract/barcode decoder). *Needs:* confirmation of exactly what is installed so
    `/healthz` capability detection has a known-good target. If a required capability is absent,
    Maxx/infra decides whether to add it.
