"""Sign-in on BTP, without BTP: tokens signed with a local RSA key stand in for XSUAA.

Covers the four validation rules (signature, expiry, issuer, audience), the mapping from token to
document audiences, the fail-closed server start, and the OAuth metadata that MCP clients discover.
"""
import asyncio
import json
import os
import sys
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from xsuaa import XsuaaVerifier, XsuaaAccessToken, audiences_for, country_of, xsuaa_binding  # noqa: E402

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC_PEM = KEY.public_key().public_bytes(serialization.Encoding.PEM,
                                           serialization.PublicFormat.SubjectPublicKeyInfo).decode()
URL = "https://cab3acb2trial.authentication.ap21.hana.ondemand.com"
CLIENT = "sb-northwind-service-cab3acb2trial-dev!t123"
BINDING = {"url": URL, "clientid": CLIENT, "clientsecret": "not-used-by-the-verifier", "verificationkey": PUBLIC_PEM,
           "xsappname": "northwind-service-cab3acb2trial-dev!t123"}


def token(key=KEY, **changes) -> str:
    claims = {"iss": URL + "/oauth/token", "exp": int(time.time()) + 3600, "cid": CLIENT, "client_id": CLIENT,
              "aud": [CLIENT, "openid"], "scope": ["openid", BINDING["xsappname"] + ".SalesRegion"],
              "user_name": "steven@example.com", "email": "steven@example.com",
              "xs.user.attributes": {"country": ["UK"]}, "ext_attr": {"enhancer": "XSUAA"}}
    claims.update(changes)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "key-1"})


def verify(tok: str):
    return asyncio.run(XsuaaVerifier(BINDING).verify_token(tok))


# ------------------------------------------------------------------ the four rules
def test_valid_token_is_accepted_with_scopes_and_claims():
    t = verify(token())
    assert isinstance(t, XsuaaAccessToken)
    assert t.client_id == CLIENT and BINDING["xsappname"] + ".SalesRegion" in t.scopes
    assert t.claims["user_name"] == "steven@example.com" and country_of(t.claims) == "UK"


def test_wrong_signature_is_refused():
    assert verify(token(key=OTHER_KEY)) is None


def test_expired_token_is_refused():
    assert verify(token(exp=int(time.time()) - 600)) is None


def test_token_from_another_tenant_is_refused():
    assert verify(token(iss="https://evil.authentication.ap21.hana.ondemand.com/oauth/token")) is None


def test_token_issued_to_another_application_is_refused():
    other = "sb-some-other-app!t999"
    assert verify(token(cid=other, client_id=other, aud=[other])) is None


def test_garbage_is_refused():
    assert verify("not.a.token") is None and verify("") is None


# ------------------------------------------------------------------ token -> document audiences
@pytest.mark.parametrize("scopes, country, expected", [
    (["openid", "x!t1.SalesHQ"], None, ("all-staff", "sales", "sales-seattle")),        # Nancy: HQ, no attribute
    (["openid", "x!t1.SalesHQ"], "USA", ("all-staff", "sales", "sales-seattle")),
    (["openid", "x!t1.SalesRegion"], "UK", ("all-staff", "sales", "sales-london")),      # Steven
    (["openid", "x!t1.SalesRegion"], "USA", ("all-staff", "sales", "sales-seattle")),
    (["openid", "x!t1.SalesRegion"], None, ("all-staff", "sales")),                      # role without a country
    (["openid"], "UK", ("all-staff",)),                                                  # signed in, no sales role
])
def test_audiences_follow_role_and_country(scopes, country, expected):
    assert audiences_for(scopes, country) == expected


def test_identity_builds_the_user_from_the_verified_token(monkeypatch):
    monkeypatch.delenv("DEV_MODE", raising=False)
    import identity
    from mcp.server.auth.middleware import auth_context
    t = verify(token())
    monkeypatch.setattr(auth_context, "get_access_token", lambda: t)
    user = identity.resolve_user({"authorization": "Bearer " + t.token})
    assert user.name == "steven@example.com"
    assert user.audiences == ("all-staff", "sales", "sales-london")
    assert user.bearer_token == t.token and user.backend_auth is None    # the token is forwarded, no password


def test_identity_without_a_verified_token_fails_closed(monkeypatch):
    monkeypatch.delenv("DEV_MODE", raising=False)
    import identity
    from mcp.server.auth.middleware import auth_context
    monkeypatch.setattr(auth_context, "get_access_token", lambda: None)
    with pytest.raises(identity.NotSignedIn):
        identity.resolve_user({"authorization": "Bearer forged"})


# ------------------------------------------------------------------ server start-up and metadata
def test_binding_is_found_in_vcap_services(monkeypatch):
    monkeypatch.setenv("VCAP_SERVICES", json.dumps({"xsuaa": [{"name": "northwind-service-auth", "tags": ["xsuaa"],
                                                                "credentials": BINDING}]}))
    assert xsuaa_binding()["clientid"] == CLIENT


def test_server_refuses_to_start_without_binding_outside_dev_mode(monkeypatch):
    monkeypatch.delenv("DEV_MODE", raising=False)
    monkeypatch.delenv("VCAP_SERVICES", raising=False)
    monkeypatch.setenv("MCP_PUBLIC_URL", "https://example.test")
    import server
    with pytest.raises(SystemExit):
        server.build("advisor")


def test_metadata_routes_and_401_challenge(monkeypatch):
    monkeypatch.delenv("DEV_MODE", raising=False)
    monkeypatch.setenv("VCAP_SERVICES", json.dumps({"xsuaa": [{"name": "northwind-service-auth", "tags": ["xsuaa"],
                                                                "credentials": BINDING}]}))
    monkeypatch.setenv("MCP_PUBLIC_URL", "https://mcp.example.test/")
    import server
    from starlette.testclient import TestClient
    app = server.build("advisor").streamable_http_app()
    with TestClient(app) as c:
        assert c.get("/health").json()["signed_in_required"] is True

        pr = c.get("/.well-known/oauth-protected-resource/mcp").json()        # served by the MCP SDK
        assert pr["resource"] == "https://mcp.example.test/mcp"
        assert pr["authorization_servers"] == ["https://mcp.example.test/"]
        assert c.get("/.well-known/oauth-protected-resource").json() == \
               c.get("/.well-known/oauth-protected-resource/").json()
        assert c.get("/.well-known/oauth-protected-resource").json()["resource"] == "https://mcp.example.test/mcp"

        asm = c.get("/.well-known/oauth-authorization-server").json()         # points at XSUAA
        assert asm == c.get("/.well-known/oauth-authorization-server/").json()
        assert asm["issuer"] == "https://mcp.example.test/"
        assert asm["authorization_endpoint"] == URL + "/oauth/authorize"
        assert asm["token_endpoint"] == URL + "/oauth/token"
        assert "registration_endpoint" not in asm and "S256" in asm["code_challenge_methods_supported"]

        r = c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert r.status_code == 401
        assert 'resource_metadata="https://mcp.example.test/.well-known/oauth-protected-resource/mcp"' in r.headers["www-authenticate"]

        r = c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                   headers={"Authorization": "Bearer " + token(key=OTHER_KEY)})
        assert r.status_code == 401                                             # forged token: still no access

        # a valid token gets through the middleware to the MCP handshake
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}}
        r = c.post("/mcp", json=init, headers={"Authorization": "Bearer " + token(),
                                             "Accept": "application/json, text/event-stream"})
        assert r.status_code == 200, r.text
