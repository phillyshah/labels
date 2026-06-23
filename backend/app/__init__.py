"""FastAPI web service for the label-approval app.

One service (per the user's `rumors` convention) that:
  - serves the processor contract (GET /healthz, POST /process)  [docs/07]
  - serves the reviewer-facing API the React/Vite SPA calls       [docs/06]
  - persists to Supabase Postgres + Storage when configured, else a local fallback store
"""
