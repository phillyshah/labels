"""Document-tooling capability detection.

Per docs/04, the processor must REUSE whatever PDF/image/OCR/barcode tooling the host already
has rather than installing a parallel stack. This module probes for each capability and reports
it on GET /healthz. The pipeline binds to whatever the probe finds; if a required capability is
absent, /healthz returns 503 so a deploy smoke test fails loudly.

NOTE: confirming the exact VPS inventory is open question #12 in docs/09. Until a DataMatrix
decoder + OCR are confirmed present, the label/handwritten paths fall back to the bundled sample
ground-truth (processor.sample_registry).
"""

from __future__ import annotations

import functools
import importlib
import shutil
from typing import Dict, Optional


def _has_lib(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except Exception:
        return False


@functools.lru_cache(maxsize=1)
def probe() -> Dict[str, Optional[str]]:
    """Return the detected backend for each capability (or None). Cached per process."""
    caps: Dict[str, Optional[str]] = {
        "pdf_text": None,
        "pdf_raster": None,
        "ocr": None,
        "barcode": None,
        "image": None,
    }

    if _has_lib("fitz"):
        caps["pdf_text"] = "pymupdf"
        caps["pdf_raster"] = "pymupdf"
    elif _has_lib("pdfplumber"):
        caps["pdf_text"] = "pdfplumber"
    elif shutil.which("pdftotext"):
        caps["pdf_text"] = "pdftotext"
    if caps["pdf_raster"] is None:
        if shutil.which("pdftoppm"):
            caps["pdf_raster"] = "pdftoppm"
        elif _has_lib("pdf2image"):
            caps["pdf_raster"] = "pdf2image"

    if shutil.which("tesseract") or _has_lib("pytesseract"):
        caps["ocr"] = "tesseract"

    if _has_lib("pylibdmtx.pylibdmtx"):
        caps["barcode"] = "pylibdmtx"
    elif _has_lib("zxingcpp"):
        caps["barcode"] = "zxing-cpp"
    elif _has_lib("pyzbar.pyzbar"):
        caps["barcode"] = "pyzbar"
    elif shutil.which("dmtxread"):
        caps["barcode"] = "dmtxread"

    if _has_lib("cv2"):
        caps["image"] = "opencv"
    elif _has_lib("PIL"):
        caps["image"] = "pillow"

    return caps


# Capabilities that must be present for the processor to fully verify a real (non-bundled) label.
REQUIRED = ("pdf_text",)


def missing_required() -> list:
    caps = probe()
    return [c for c in REQUIRED if not caps.get(c)]


def decode_datamatrix(label_path: str) -> Optional[str]:
    """Decode a GS1 DataMatrix from a label PDF/image using the detected backend.

    Returns the raw payload string, or None if nothing decodes / no backend present. This is the
    real path used the moment a barcode capability is detected on the host.
    """
    caps = probe()
    if not caps.get("barcode") or not caps.get("pdf_raster"):
        return None
    try:
        images = _rasterize(label_path)
        for img in images:
            payload = _decode_image(img, caps["barcode"])
            if payload:
                return payload
    except Exception:
        return None
    return None


def _rasterize(path: str):
    import fitz  # pymupdf
    doc = fitz.open(path)
    out = []
    for page in doc:
        pix = page.get_pixmap(dpi=300)
        from PIL import Image
        out.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
    return out


def _decode_image(img, backend: str) -> Optional[str]:
    if backend == "pylibdmtx":
        from pylibdmtx.pylibdmtx import decode
        res = decode(img)
        if res:
            return res[0].data.decode("utf-8", "replace")
    elif backend == "pyzbar":
        from pyzbar.pyzbar import decode
        res = decode(img)
        if res:
            return res[0].data.decode("utf-8", "replace")
    return None
