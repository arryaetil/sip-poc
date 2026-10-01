"""Issue short-lived, single-use entry links for the private Developer service."""

import base64
import hashlib
import hmac
import json
import os
import time
from uuid import uuid4


class DeveloperUnavailable(RuntimeError):
    pass


def signed_link(email: str) -> str:
    allowed = os.getenv("SIP_DEVELOPER_EMAIL", "").strip().casefold()
    public = os.getenv("OPENCODE_DEVELOPER_PUBLIC_URL", "").strip().rstrip("/")
    secret = os.getenv("DEVELOPER_HANDOFF_SECRET", "").strip()
    if not (allowed and public.startswith("https://") and secret):
        raise DeveloperUnavailable("De Developer is nog niet beschikbaar.")
    if not hmac.compare_digest(email.casefold(), allowed):
        raise PermissionError("Dit account heeft geen toegang tot de Developer.")
    claims = {"sub": hashlib.sha256(allowed.encode()).hexdigest()[:24], "exp": int(time.time()) + 120, "jti": uuid4().hex, "next": "/"}
    body = base64.urlsafe_b64encode(json.dumps(claims, separators=(",", ":")).encode()).rstrip(b"=").decode()
    signature = base64.urlsafe_b64encode(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    return f"{public}/__sip/enter?t={body}.{signature}"
