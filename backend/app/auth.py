"""Authentication for V1: a single shared password gated behind a swappable interface.

The reviewer logs in with the shared APP_PASSWORD and, at sign time, types their name -- that
typed name + timestamp becomes the signer of record (WI052 3.7) until per-user Supabase Auth is
introduced. Everything reviewer-identity-related flows through `current_reviewer()`, so swapping
in Supabase Auth later is additive: replace token issuance/verification, keep the call sites.
"""

from __future__ import annotations

import hmac
from typing import Optional

from fastapi import Header, HTTPException, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .config import settings


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings().session_secret, salt="label-approval-session")


def login(password: str) -> Optional[str]:
    """Return a signed session token if the shared password is correct, else None."""
    if hmac.compare_digest(password or "", settings().app_password):
        return _serializer().dumps({"role": "reviewer"})
    return None


def current_reviewer(authorization: str = Header(default="")) -> dict:
    """FastAPI dependency: validate the Bearer session token; raise 401 otherwise."""
    token = authorization[7:] if authorization.lower().startswith("bearer ") else authorization
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")
    try:
        data = _serializer().loads(token, max_age=settings().session_ttl_seconds)
    except SignatureExpired:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session expired")
    except BadSignature:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid session")
    return {"role": data.get("role", "reviewer")}


def require_processor_secret(x_processor_secret: str = Header(default="")) -> None:
    """FastAPI dependency guarding the internal POST /process route (docs/07)."""
    expected = settings().processor_shared_secret
    if not hmac.compare_digest(x_processor_secret or "", expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid processor secret")
