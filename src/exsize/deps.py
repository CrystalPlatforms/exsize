from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from exsize.database import get_db
from exsize.models import ApiToken, Subscription, User
from exsize.security import decode_access_token, verify_password

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        user_id = decode_access_token(credentials.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


optional_bearer_scheme = HTTPBearer(auto_error=False)


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """Like :func:`get_current_user` but returns ``None`` when no/invalid token is
    present instead of raising — used by endpoints that also accept a shared secret."""
    if credentials is None:
        return None
    try:
        user_id = decode_access_token(credentials.credentials)
    except Exception:
        return None
    return db.query(User).filter(User.id == user_id).first()


def has_sizepass(family_id: int | None, db: Session) -> bool:
    if family_id is None:
        return False
    return db.query(Subscription).filter(
        Subscription.family_id == family_id,
        Subscription.status == "active",
    ).first() is not None


def resolve_api_token_user(db: Session, raw_token: str) -> User | None:
    """Match a raw API token (``exs_...``) against stored bcrypt hashes.

    Returns the owner of the first active (non-revoked) token that verifies,
    or None. Shared by the Cryplo API and the MCP server (issue #66).
    """
    for api_token in db.query(ApiToken).filter(ApiToken.revoked_at.is_(None)).all():
        if verify_password(raw_token, api_token.token_hash):
            return db.query(User).filter(User.id == api_token.user_id).first()
    return None
