"""
Shared pytest configuration.

The tests import from a `processor` package (the service the coding team builds, per
docs/01-architecture.md and docs/04-processing-pipeline.md). To run the tests, the team's
`processor/` source directory must be importable -- either:

  1. install it as an editable package:   pip install -e processor/
  2. or add it to PYTHONPATH:              PYTHONPATH=processor pytest ...

The import contract (function signatures the tests rely on) is documented in tests/README.md.
Until the processor exists, the tests will fail at import -- that is expected; they define the
target the implementation must satisfy.
"""

import os
import sys

# Allow `processor` to be found if the team places it at repo-root/processor.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSOR_DIR = os.path.join(REPO_ROOT, "processor")
if os.path.isdir(PROCESSOR_DIR) and PROCESSOR_DIR not in sys.path:
    sys.path.insert(0, REPO_ROOT)  # so `import processor.xxx` works
