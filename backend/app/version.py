"""Single source of truth for the app version and changelog.

Increment VERSION on every meaningful release. Keep CHANGELOG in reverse
chronological order (newest first). The /version API, the header "What's New"
panel, and the footer version badge all read from here.

Notes are written in plain, user-facing language — they are what shows in the
"What's New" panel. The developer-facing record lives in CHANGELOG.md at the
repo root.
"""

VERSION = "1.5.0"

CHANGELOG: list[dict] = [
    {
        "version": "1.5.0",
        "date": "2026-06-25",
        "notes": [
            "The Rules screen is now editable: turn each data-driven check (GTIN, "
            "description, IFU, static label content) on or off and enter its values "
            "right in the app — no more hand-editing config files",
            "Activating a check makes it run for real; while a check is left off it "
            "stays 'Deferred' and the reviewer signs off on it manually, exactly as "
            "before. Every rule change is recorded in the audit log",
        ],
    },
    {
        "version": "1.4.0",
        "date": "2026-06-25",
        "notes": [
            "Added a 'What's New' panel (this one) so every release's changes are "
            "visible in the app, with the current version shown in the footer",
            "Added an in-app user guide: click the '?' button in the header to open "
            "a quick guide to running a review, reading the verdict, and training "
            "the tool — no need to leave the page",
        ],
    },
    {
        "version": "1.3.0",
        "date": "2026-06-24",
        "notes": [
            "Training can now auto-score a batch against known-correct results: turn "
            "on 'I have the expected results', enter the expected verdict and "
            "per-check outcomes, and the tool scores its own accuracy in one click — "
            "or keep rating each check by hand",
            "Added AI-suggested rule edits: from the cases where you disagreed with "
            "the tool, it can draft concrete, reviewable changes to the rules (it "
            "only suggests — nothing is applied automatically)",
        ],
    },
    {
        "version": "1.2.0",
        "date": "2026-06-24",
        "notes": [
            "New 'Training' tab: re-run a past batch, rate each check (correct / "
            "partial / wrong) with notes, and build up a labeled corpus the tool "
            "learns from",
            "Added an accuracy dashboard showing overall and per-check agreement "
            "between the tool and your ratings, updating as you train",
        ],
    },
    {
        "version": "1.1.0",
        "date": "2026-06-24",
        "notes": [
            "Uploading documents is now drag-and-drop, with each required and "
            "optional document clearly slotted",
            "The tool now checks that each uploaded document is the expected type "
            "and warns you up front when something looks mismatched, before it runs "
            "the checks",
            "The discrepancy report now opens with a plain-language summary of what "
            "was found and why, not just a table of check results",
        ],
    },
    {
        "version": "1.0.0",
        "date": "2026-06-23",
        "notes": [
            "Initial release: upload a label packet and get automated approval "
            "checks (A–G) with a clear APPROVE / APPROVE-WITH-FLAGS / REJECT verdict",
            "Cross-checks the label against the batch and sterilization records, "
            "and reads barcodes (GS1 DataMatrix) for the device identity",
            "Generates an approval bundle and a discrepancy report as PDFs, ready "
            "to hand off",
        ],
    },
]
