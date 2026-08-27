"""Google OAuth helpers shared by the web login and the MCP server.

Web login (authorization-code flow): the browser is redirected to Google's
consent screen and comes back to ``/api/auth/google/callback``; the callback
maps the verified email onto an ExSize account (exactly like the MCP path) and
hands the app JWT to the frontend via a URL fragment.

Account mapping: an existing account wins (matched by email); a first-time
email auto-creates a child account with language pl and an unusable random
password. PII (email) is only ever persisted in the database, never logged.
"""

import os
import secrets
import time
from urllib.parse import urlencode, urlsplit

import httpx
import jwt
from sqlalchemy.orm import Session

from exsize.models import User
from exsize.security import hash_password

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

STATE_TTL_SECONDS = 600


def configured() -> bool:
    return bool(os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET"))


def server_origin() -> str:
    """Public origin of this backend, from MCP_BASE_URL (path stripped)."""
    raw = os.environ.get("MCP_BASE_URL", "")
    parsed = urlsplit(raw)
    if not parsed.scheme or not parsed.netloc:
        raise RuntimeError(
            "MCP_BASE_URL is missing or not an absolute URL — set it to the "
            "public site origin, e.g. https://exsize-prod.onrender.com"
        )
    return f"{parsed.scheme}://{parsed.netloc}"


def redirect_uri() -> str:
    return f"{server_origin()}/api/auth/google/callback"


def frontend_origin() -> str:
    """First allowed CORS origin doubles as the SPA's public URL."""
    origins = os.environ.get("CORS_ORIGINS", "https://exsize.pages.dev")
    return origins.split(",")[0].strip().rstrip("/")


def _state_secret() -> str:
    return os.environ.get("ADMIN_SECRET", "dev-insecret-state-key")


def sign_state() -> str:
    """Short-lived signed state (CSRF guard + round-trip proof of our own flow)."""
    return jwt.encode(
        {"nonce": secrets.token_urlsafe(16), "exp": int(time.time()) + STATE_TTL_SECONDS},
        _state_secret(),
        algorithm="HS256",
    )


def verify_state(state: str | None) -> bool:
    if not state:
        return False
    try:
        jwt.decode(state, _state_secret(), algorithms=["HS256"])
        return True
    except Exception:
        return False


def build_authorize_url(state: str) -> str:
    params = urlencode({
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": "openid email",
        "state": state,
        "prompt": "select_account",
    })
    return f"{GOOGLE_AUTH_URL}?{params}"


async def exchange_code(code: str) -> dict:
    """Swap the authorization code for a Google access token and read the
    verified profile (email). Talks to Google only over HTTPS."""
    async with httpx.AsyncClient(timeout=10) as client:
        token_response = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "redirect_uri": redirect_uri(),
            "grant_type": "authorization_code",
        })
        token_response.raise_for_status()
        access_token = token_response.json()["access_token"]
        profile = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        profile.raise_for_status()
        return profile.json()


def resolve_google_user(db: Session, email: str) -> User:
    """Map a verified Google email onto an ExSize account.

    An existing account wins (register in the web app with the same email
    BEFORE the first Google login to adopt it); unknown emails get an
    auto-created child account with language pl and a random unusable password
    (web password login stays impossible for it)."""
    user = db.query(User).filter(User.email == email.lower()).first()
    if user is None:
        user = User(
            email=email.lower(),
            password_hash=hash_password(secrets.token_urlsafe(32)),
            role="child",
            language="pl",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user
