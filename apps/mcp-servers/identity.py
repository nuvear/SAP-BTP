"""Who is asking? Every tool call starts here.

Two modes:
  DEV_MODE=1   Local development. The user comes from the 'X-Dev-User' header, or from the DEV_USER
               environment variable. The users match the mocked users of the CAP service.
  otherwise    SAP BTP. The user comes from the XSUAA bearer token that the MCP SDK's auth middleware has
               already verified with xsuaa.XsuaaVerifier (signature, expiry, issuer, audience). Without a
               verified token there is no user, and every tool call fails closed.

The servers never decide which ROWS a user may see. They pass the identity on, and the CAP service decides.
The Policy server does filter DOCUMENTS by audience, because the documents live in its own store.
"""
from __future__ import annotations
import os
from dataclasses import dataclass

DEV_USERS = {
    # name: (audiences for documents, basic-auth password for the local CAP service)
    "nancy":  (["all-staff", "sales", "sales-seattle"], "nancy"),    # Seattle, role SalesHQ: sees all orders
    "steven": (["all-staff", "sales", "sales-london"], "steven"),    # London, role SalesRegion: UK orders only
}


@dataclass(frozen=True)
class User:
    name: str
    audiences: tuple[str, ...]
    backend_auth: tuple[str, str] | None      # basic auth for the local CAP service
    bearer_token: str | None = None           # on BTP: the user's token, forwarded to the CAP service


class NotSignedIn(Exception):
    pass


def resolve_user(headers: dict[str, str] | None) -> User:
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    if os.environ.get("DEV_MODE") == "1":
        name = headers.get("x-dev-user") or os.environ.get("DEV_USER")
        if name not in DEV_USERS:
            raise NotSignedIn("Unknown or missing development user.")
        audiences, password = DEV_USERS[name]
        return User(name, tuple(audiences), (name, password))
    # BTP: the auth middleware put the verified token into the request context. No token, no user.
    from mcp.server.auth.middleware.auth_context import get_access_token
    from xsuaa import XsuaaAccessToken, audiences_for, country_of
    token = get_access_token()
    if not isinstance(token, XsuaaAccessToken):
        raise NotSignedIn("Sign in to SAP BTP first. This server accepts only verified XSUAA tokens.")
    claims = token.claims
    name = claims.get("user_name") or claims.get("email") or claims.get("sub") or "unknown"
    return User(name, audiences_for(token.scopes, country_of(claims)), None, bearer_token=token.token)


def headers_from_context(ctx) -> dict[str, str]:
    """Best effort: HTTP transports expose the request; stdio and in-memory transports do not."""
    try:
        return dict(ctx.request_context.request.headers)
    except Exception:
        return {}
