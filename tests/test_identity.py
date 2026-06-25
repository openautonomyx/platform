import base64
import json

import pytest

from ard import DiscoveryApi, Registry, agent_card
from ard.card import AgentCard, CardError
from ard.identity import AuthXIdentity, check_identity, secure_with_authx, unverified_claims


def _jwt(claims: dict) -> str:
    def b64(o):
        return base64.urlsafe_b64encode(json.dumps(o).encode()).decode().rstrip("=")

    return f"{b64({'alg': 'none'})}.{b64(claims)}.sig"


def test_identity_validate():
    AuthXIdentity(agent_id="agx:a", issuer="https://id.x").validate()
    with pytest.raises(ValueError):
        AuthXIdentity(agent_id="", issuer="https://id.x").validate()


def test_secured_card_roundtrips_with_a2a_security():
    ident = AuthXIdentity("agx:openagx/echo", "https://authx.openagx.dev", audience="ecosystem")
    c = agent_card("echo", "d", "http://x", kind="skill", skills=["echo"], identity=ident, secured=True)
    d = c.to_dict()
    assert "authx-id" in d["securitySchemes"]
    assert d["security"] == [{"authx-id": []}]
    assert d["x-ard"]["identity"]["agentId"] == "agx:openagx/echo"
    c2 = AgentCard.from_dict(d)
    assert c2.identity.issuer == "https://authx.openagx.dev"
    assert c2.to_dict() == d  # full roundtrip incl. identity + security


def test_security_requiring_undefined_scheme_is_rejected():
    c = AgentCard(name="x", description="d", url="u", version="1", security=[{"authx-id": []}])
    with pytest.raises(CardError):
        c.validate()


def test_discover_by_issuer():
    reg = Registry()
    ident = AuthXIdentity("agx:a", "https://authx.openagx.dev")
    reg.register(agent_card("A", "d", "http://x", skills=["s"], identity=ident, secured=True))
    reg.register(agent_card("B", "d", "http://x", skills=["s"]))
    assert {c.name for c in reg.query(issuer="https://authx.openagx.dev")} == {"A"}
    api = DiscoveryApi(reg)
    status, data = api.handle("GET", "/agents?issuer=https%3A%2F%2Fauthx.openagx.dev")
    assert status == 200 and [c["name"] for c in data] == ["A"]


def test_token_check_matches_issuer_and_audience():
    ident = AuthXIdentity("agx:a", "https://authx.openagx.dev", audience="eco")
    assert check_identity(_jwt({"iss": "https://authx.openagx.dev", "aud": "eco"}), ident) is True
    assert check_identity(_jwt({"iss": "https://evil", "aud": "eco"}), ident) is False
    assert check_identity(_jwt({"iss": "https://authx.openagx.dev", "aud": "other"}), ident) is False
    assert unverified_claims("garbage") == {}


def test_secure_with_authx_builds_scheme_and_requirement():
    schemes, security = secure_with_authx(AuthXIdentity("agx:a", "https://id.x"))
    assert "authx-id" in schemes and schemes["authx-id"]["type"] == "openIdConnect"
    assert security == [{"authx-id": []}]
