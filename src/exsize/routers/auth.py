import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from exsize.database import get_db
from exsize.deps import get_current_user
from exsize.models import User
from exsize.security import create_access_token, hash_password, verify_password
from exsize.services import google_oauth

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    password: str
    role: Literal["parent", "child"]  # admin cannot self-register
    language: Literal["en", "pl"] = "en"
    date_of_birth: str | None = None


class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    language: str

    model_config = {"from_attributes": True}


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        role=body.role,
        language=body.language,
        date_of_birth=body.date_of_birth,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user.id)
    return TokenResponse(access_token=token)


class AdminLoginRequest(BaseModel):
    admin_secret: str


@router.post("/admin-login", response_model=TokenResponse)
def admin_login(body: AdminLoginRequest, db: Session = Depends(get_db)):
    expected = os.environ.get("ADMIN_SECRET")
    if not expected or body.admin_secret != expected:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    admin_user = db.query(User).filter(User.role == "admin").first()
    if not admin_user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(admin_user.id)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return user


# --- Google login (redirect flow; account mapping shared with MCP, issue #76) ---


class GoogleStatusResponse(BaseModel):
    enabled: bool


@router.get("/google/status", response_model=GoogleStatusResponse)
def google_status():
    return GoogleStatusResponse(enabled=google_oauth.configured())


@router.get("/google/authorize")
def google_authorize():
    """Send the browser to Google's consent screen (302)."""
    if not google_oauth.configured():
        raise HTTPException(status_code=404, detail="Google login is not configured")
    return RedirectResponse(google_oauth.build_authorize_url(google_oauth.sign_state()))


@router.get("/google/callback")
async def google_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    """Google redirects here; hand the app JWT to the SPA via a URL fragment.

    Every failure lands on the frontend with ?google_error=... instead of a
    bare error page, so the user always ends up back in the app.
    """
    frontend = google_oauth.frontend_origin()

    def _back_with_error(reason: str) -> RedirectResponse:
        return RedirectResponse(f"{frontend}/?google_error={reason}")

    if error:
        return _back_with_error(error)
    if not google_oauth.configured() or not code or not google_oauth.verify_state(state):
        return _back_with_error("invalid_state")

    try:
        profile = await google_oauth.exchange_code(code)
    except Exception:
        return _back_with_error("google_exchange_failed")
    email = profile.get("email")
    if not email:
        return _back_with_error("no_email")

    user = google_oauth.resolve_google_user(db, email)
    token = create_access_token(user.id)
    return RedirectResponse(f"{frontend}/#token={token}")
