"""AuthX-ID — agent identity for the ecosystem (openagx/AuthX-ID).

A discoverable agent can carry an AuthX-ID *identity* and declare that callers
must authenticate with an AuthX-ID token. This is layered on the A2A card's
standard ``securitySchemes`` / ``security`` (so any A2A consumer understands it),
plus an ``x-ard.identity`` block naming the agent's stable AuthX-ID.

NOTE: token *verification* here is MVP — it reads (unverified) JWT claims and
checks issuer/audience. Real verification fetches the issuer's JWKS and checks
the signature; that follows the openagx/AuthX-ID spec and is a future step.
"""
from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass

AUTHX_SCHEME = "authx-id"


@dataclass
class AuthXIdentity:
    agent_id: str  # stable AuthX-ID, e.g. "agx:openagx/echo-agent"
    issuer: str  # AuthX-ID issuer URL
    audience: str | None = None

    def validate(self) -> "AuthXIdentity":
        if not self.agent_id:
            raise ValueError("AuthXIdentity: missing agent_id")
        if not self.issuer:
            raise ValueError("AuthXIdentity: missing issuer")
        return self

    def to_dict(self) -> dict:
        d = {"agentId": self.agent_id, "issuer": self.issuer}
        if self.audience:
            d["audience"] = self.audience
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "AuthXIdentity":
        return cls(
            agent_id=d.get("agentId") or d.get("agent_id", ""),
            issuer=d.get("issuer", ""),
            audience=d.get("audience"),
        )


def authx_scheme(issuer: str, audience: str | None = None) -> dict:
    """An A2A/OpenAPI security scheme representing AuthX-ID (OIDC bearer)."""
    scheme: dict = {
        "type": "openIdConnect",
        "openIdConnectUrl": issuer.rstrip("/") + "/.well-known/openid-configuration",
        "x-authx-id": {"audience": audience} if audience else True,
    }
    return scheme


def require_authx() -> list[dict]:
    """A security-requirement list referencing the AuthX-ID scheme."""
    return [{AUTHX_SCHEME: []}]


def secure_with_authx(identity: AuthXIdentity) -> tuple[dict, list[dict]]:
    """Return ``(securitySchemes, security)`` declaring AuthX-ID is required."""
    return {AUTHX_SCHEME: authx_scheme(identity.issuer, identity.audience)}, require_authx()


def unverified_claims(token: str) -> dict:
    """Decode a JWT payload WITHOUT verifying the signature (MVP only)."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, binascii.Error, json.JSONDecodeError, ValueError):
        return {}


def check_identity(token: str, identity: AuthXIdentity) -> bool:
    """MVP check: issuer (and audience, if set) match the agent's identity.

    WARNING: does not verify the token signature — see the module note.
    """
    claims = unverified_claims(token)
    if claims.get("iss") != identity.issuer:
        return False
    if identity.audience:
        aud = claims.get("aud")
        auds = aud if isinstance(aud, list) else [aud]
        if identity.audience not in auds:
            return False
    return True
