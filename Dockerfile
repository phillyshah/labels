# Maxx Label Approval — single image: builds the Vite SPA, then serves it + the API from FastAPI.
# Deploy style follows the user's `usage` repo (Docker + Traefik). NOTE: prepared, not yet deployed.

# ---- stage 1: build the React/Vite frontend ----
FROM node:20-slim AS frontend
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build         # outputs /web/dist

# ---- stage 2: python backend + processor ----
FROM python:3.11-slim AS app
# System tooling the processor binds to (poppler/tesseract/zbar/dmtx). This is the one image
# where we DO install the document stack; on a shared VPS confirm these are acceptable (Q#12).
RUN apt-get update && apt-get install -y --no-install-recommends \
        poppler-utils tesseract-ocr libzbar0 libdmtx0t64 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# App source.
COPY processor/ ./processor/
COPY backend/ ./backend/
COPY config/ ./config/
COPY reference-documents/ ./reference-documents/

# Built SPA -> served by FastAPI at "/".
COPY --from=frontend /web/dist ./backend/static

ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app
EXPOSE 8000
# Healthcheck mirrors docs/02: 200 when capabilities present, 503 when a binary is missing.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz').status==200 else 1)" || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
