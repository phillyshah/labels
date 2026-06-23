"""Label-approval processor package.

Implements the import contract the test suite targets (see tests/README.md):

    processor.barcode    parse_gs1, gs1_date_to_iso, decode_label_barcodes
    processor.extraction normalize_ref/lot/qty, parse_date_to_iso, extract_fields
    processor.checks      run_checks, resolve_verdict
    processor.pipeline    process_submission
    processor.capabilities probe()  -> document-tooling capability map for /healthz

The engine is deterministic: same input + same rules => same verdict.
"""
