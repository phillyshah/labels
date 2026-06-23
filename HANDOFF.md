# Maxx Orthopedics — Label Approval Automation: Project Handoff

This package is a complete build brief for a **form-driven web application** that automates
the Meril-label approval process defined in Work Instruction **WI052 (R01), Section 3.0**.

A Quality reviewer drops in the documents for a batch, clicks **Go**, and receives a
**PASS / FAIL / FLAG** scorecard plus a signable approval record.

---

## 1. What this package is

This is **not** finished source code. It is a build specification: the source/reference
documents, the rules the system must enforce, the architecture, and a full test suite that the
finished code must pass. Your job is to implement the system described in `docs/` so that all
tests in `tests/` pass and the deployment target in `docs/02-deployment-vps-traefik.md` is met.

## 2. How to process this zip

1. **Unzip** into a clean working directory.
2. **Read in this order** (each doc assumes you've read the earlier ones):
   - `docs/00-project-overview.md` — what we're building and why
   - `docs/01-architecture.md` — components and how they fit together
   - `docs/02-deployment-vps-traefik.md` — the Hostinger VPS + Traefik + subdomain target
   - `docs/03-supabase-schema.md` — database, storage buckets, auth
   - `docs/04-processing-pipeline.md` — the document-processing service
   - `docs/05-checks-specification.md` — **the core**: every check the engine must run
   - `docs/06-frontend-spec.md` — the form-driven UI
   - `docs/07-api-spec.md` — contract between frontend and processor
   - `docs/08-testing-spec.md` — how to run and extend the test suite
   - `docs/09-open-questions-and-config.md` — decisions still owned by Maxx Quality
3. **Study the reference documents** in `reference-documents/`. The `samples/` folder is one
   real, fully worked batch (V11022719 in sterile lot M26-179). The expected output for that
   batch is the golden fixture the integration test asserts against.
4. **Stand up the stack** per the architecture and deployment docs.
5. **Implement** the processor and frontend until `tests/` passes.
6. **Deploy** behind Traefik on the subdomain confirmed with Maxx (see §9 open questions).

## 3. Folder map

```
maxx-label-approval-handoff/
├── README.md                     <- you are here
├── docs/                         <- the build specification (read in order)
├── reference-documents/
│   ├── WI052_..._R01.pdf         <- the governing work instruction
│   ├── WI052-F1_..._R01.pdf      <- the paper approval-record form this app replaces
│   ├── samples/                  <- one real worked batch (the test gold standard)
│   └── README.md                 <- describes each document and its role
├── config/
│   └── rules.example.yaml        <- the configurable rule set (MXO-PP00001/00006 placeholder)
└── tests/                        <- the suite the finished build must pass
    ├── fixtures/                 <- golden expected results
    ├── unit/  integration/  e2e/
    └── README.md
```

## 4. Hard constraints (do not deviate without Maxx sign-off)

- **This is a medical-device quality record system.** Every automated verdict must be
  traceable, every value must cite its source document, and the system **never auto-approves**
  a label as a final regulated act — a human applies the final signature. See
  `docs/05-checks-specification.md` §"Human-in-the-loop".
- **Document/image/PDF/barcode processing must reuse tooling already installed on the VPS**
  for other 90ten.life projects. Do **not** introduce new heavyweight OCR/image stacks if a
  working one is already present. Detect what's installed first (poppler, tesseract, a barcode
  decoder, etc.) and wire the processor to it. See `docs/04-processing-pipeline.md` §"Tooling".
- **MXO-PP00001 (Labeling Guidelines) and MXO-PP00006 (GTIN Codes) are NOT yet supplied.**
  Several checks depend on them. Build those checks against the config-driven rule set in
  `config/rules.example.yaml` so they activate the moment Maxx supplies the real data. Until
  then they return `DEFERRED`, not `FAIL`. See `docs/09-open-questions-and-config.md`.

## 5. Definition of done

- All unit + integration tests in `tests/` pass.
- The e2e test drives a real submission through the deployed UI and gets the expected verdict.
- The V11022719 sample, run end-to-end, produces the verdict in
  `tests/fixtures/v11022719_expected.json` (`APPROVE_WITH_FLAGS`).
- The app is reachable over HTTPS on the agreed subdomain, behind Traefik, with auth enabled.
- A completed review writes an immutable audit record and a downloadable approval bundle.

## 6. Who owns what

- **Coding team:** everything in `docs/` and `tests/`.
- **Maxx Quality:** supplies MXO-PP00001 / MXO-PP00006, resolves the open questions in
  `docs/09`, and owns the final approval signature inside the running app.
