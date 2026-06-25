# 02 — Deployment: Hostinger VPS + Traefik + 90ten.life subdomain

## Target

- **Host:** existing Hostinger VPS that already serves other 90ten.life projects.
- **Proxy:** Traefik (already managing routing/TLS on that VPS).
- **Subdomain:** a dedicated subdomain of `90ten.life` — proposed `labelcheck.90ten.life`.
  **Confirm the exact subdomain with Maxx before wiring DNS** (see `docs/09`).
- **Backend:** Supabase (cloud or self-hosted — confirm which the VPS already uses).

## DNS

Add an A/AAAA record (or CNAME if that's how the other subdomains are configured) for the
chosen subdomain pointing at the VPS, consistent with how the existing 90ten.life subdomains
resolve. Do not invent a new pattern — match the existing ones.

## Traefik integration

The VPS already runs Traefik, so **do not deploy a second proxy.** Attach the new services to
the existing Traefik using Docker provider labels. Use the same Let's Encrypt resolver,
network name, and entrypoints the other 90ten.life services already use — inspect a working
service on the VPS and copy its label conventions rather than guessing.

Illustrative labels for the `web` service (adapt names to the VPS's actual Traefik config):

```yaml
services:
  web:
    image: maxx-labelcheck-web:latest
    networks:
      - traefik            # <- use the EXISTING shared Traefik network name
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.labelcheck.rule=Host(`labelcheck.90ten.life`)"
      - "traefik.http.routers.labelcheck.entrypoints=websecure"
      - "traefik.http.routers.labelcheck.tls.certresolver=letsencrypt"  # match existing resolver name
      - "traefik.http.services.labelcheck.loadbalancer.server.port=3000"
    # ... env, depends_on, etc.

  processor:
    image: maxx-labelcheck-processor:latest
    networks:
      - traefik
    # NOTE: no traefik.enable label -> NOT publicly routed.
    # web reaches it at http://processor:8000 on the internal network.
    expose:
      - "8000"

networks:
  traefik:
    external: true          # <- the network already created by the existing Traefik stack
```

Key points:
- `processor` has **no** `traefik.enable=true` — it is internal-only.
- `web` reaches `processor` at its Docker service name on the shared network.
- Reuse the existing `certresolver` and `entrypoints` names; do not create new ones.

## Environment / secrets

Provide via the VPS's existing secret mechanism (env file mounted by compose, or whatever the
other projects use — match it). Required variables:

| Variable | Service | Purpose |
|---|---|---|
| `SUPABASE_URL` | web, processor | Supabase project URL |
| `SUPABASE_ANON_KEY` | web | Client-side auth |
| `SUPABASE_SERVICE_ROLE_KEY` | processor | Server-side writes (never exposed to browser) |
| `PROCESSOR_URL` | web | Internal URL, e.g. `http://processor:8000` |
| `PROCESSOR_SHARED_SECRET` | web, processor | Auth header on internal `/process` calls |
| `RULES_PATH` | processor | Path to the active rules YAML (see `config/`) |
| `STORAGE_BUCKET` | web, processor | Private bucket name for submissions |

Never bake secrets into images. Never ship `SUPABASE_SERVICE_ROLE_KEY` to the browser.

## Build & release

1. Build both images on CI (or on the VPS if that's the existing workflow).
2. Tag with a version, push to whatever registry the VPS pulls from.
3. `docker compose up -d` (or the existing deploy command).
4. Run DB migrations against Supabase (`docs/03`) before first traffic.
5. Smoke test: hit the health endpoints, then run the V11022719 sample through the UI.

## Health & observability

- `web`: `GET /healthz` returns 200 when it can reach Supabase + processor.
- `processor`: `GET /healthz` returns 200 and reports which document-processing binaries it
  detected on the VPS (see `docs/04` §Tooling) — useful for diagnosing a missing dependency.
- Log every run's verdict, duration, and submission id (no document contents in logs).
- Keep Traefik access logs per the VPS's existing retention.

## Rollback

Because the processor is stateless and verdicts are persisted, rolling back is just redeploying
the previous image tag. Database migrations must be backward-compatible within a release window.
