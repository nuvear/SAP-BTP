"""XSUAA bearer tokens for the MCP server: validation, and what a token says about the user.

On SAP BTP every call to the MCP server carries an OAuth access token issued by the XSUAA instance that the
data service and the MCP server share (northwind-service-auth). This module checks the token the way the
SAP libraries do, but in 80 readable lines, so that students can see every rule:

  1. signature: RS256, public key from the XSUAA JSON Web Key Set (<url>/token_keys, cached), or, when the
     key set cannot be fetched, the verificationkey that XSUAA puts into the service binding;
  2. expiry (exp) with a small clock skew;
  3. issuer: the token must come from our XSUAA tenant (iss starts with the binding's url);
  4. audience: the token must have been issued to OUR client (cid / client_id / aud contain the binding's
     clientid). A valid token for some other application is still refused.

What the token tells us (see audiences_for): the scopes (northwind-service-...!t1234.SalesHQ, .SalesRegion)
say which ROLE the user has; the attribute 'country' says which office. The CAP service applies the row rule
from the same token, so the MCP server never decides which orders a user may see: it forwards the token.

Nothing here reads a password. The client id and secret live in the XSUAA service binding (VCAP_SERVICES)
and, for the Claude connector, in Claude's connector settings, entered by the account owner.
"""
from __future__ import annotations

import os
import time
from typing import Any

import httpx
import jwt
from jwt import PyJWK
from mcp.server.auth.provider import AccessToken

OFFICE_AUDIENCE = {"USA": "sales-seattle", "UK": "sales-london"}   # country attribute -> office documents
HQ_DEFAULT_OFFICE = "sales-seattle"                                   # head office is in Seattle


class XsuaaAccessToken(AccessToken):
    """The SDK's AccessToken plus the verified claims, so tools can build the User without decoding again."""
    claims: dict[str, Any]


def xsuaa_binding() -> dict | None:
    """The XSUAA service binding from VCAP_SERVICES (Cloud Foundry), or None on a laptop."""
    import json
    vcap = os.environ.get("VCAP_SERVICES")
    if not vcap:
        return None
    for label, services in json.loads(vcap).items():
        for svc in services:
            if label == "xsuaa" or "xsuaa" in svc.get("tags", []):
                return svc["credentials"]
    return None


def audiences_for(scopes: list[str], country: str | None) -> tuple[str, ...]:
    """Which document audiences may this user read? all-staff always; 'sales' for any sales role;
    the office audience from the country attribute (SalesHQ users without a country count as Seattle)."""
    roles = {s.rsplit(".", 1)[-1] for s in scopes}
    out = ["all-staff"]
    if roles & {"SalesHQ", "SalesRegion"}:
        out.append("sales")
        office = OFFICE_AUDIENCE.get((country or "").upper())
        if office is None and "SalesHQ" in roles:
            office = HQ_DEFAULT_OFFICE
        if office:
            out.append(office)
    return tuple(out)


def country_of(claims: dict) -> str | None:
    values = (claims.get("xs.user.attributes") or {}).get("country") or []
    return values[0] if values else None


class XsuaaVerifier:
    """mcp TokenVerifier for XSUAA tokens. One instance per process; the key set is cached for an hour."""

    def __init__(self, credentials: dict, http: httpx.AsyncClient | None = None, leeway: int = 60):
        self.url = credentials["url"].rstrip("/")
        self.client_id = credentials["clientid"]
        self.verification_key = credentials.get("verificationkey")
        self.http = http or httpx.AsyncClient(timeout=5)
        self.leeway = leeway
        self._keys: dict[str, Any] = {}
        self._keys_at = 0.0

    async def _key_for(self, header: dict) -> Any:
        kid = header.get("kid")
        if kid and (time.time() - self._keys_at > 3600 or kid not in self._keys):
            try:
                r = await self.http.get(f"{self.url}/token_keys")
                r.raise_for_status()
                self._keys = {k["kid"]: PyJWK(k).key for k in r.json().get("keys", []) if "kid" in k}
                self._keys_at = time.time()
            except Exception:
                pass                                    # fall back to the binding's verificationkey below
        if kid in self._keys:
            return self._keys[kid]
        if self.verification_key:
            return self.verification_key
        return None

    async def verify_token(self, token: str) -> XsuaaAccessToken | None:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256":
                return None
            key = await self._key_for(header)
            if key is None:
                return None
            claims = jwt.decode(token, key, algorithms=["RS256"], leeway=self.leeway,
                                options={"verify_aud": False, "require": ["exp"]})
        except jwt.PyJWTError:
            return None
        if not str(claims.get("iss", "")).startswith(self.url):
            return None
        audience = set(claims.get("aud") or []) | {claims.get("cid"), claims.get("client_id")}
        if self.client_id not in audience:
            return None
        return XsuaaAccessToken(token=token, client_id=self.client_id, scopes=list(claims.get("scope") or []),
                                expires_at=int(claims["exp"]), claims=claims)
