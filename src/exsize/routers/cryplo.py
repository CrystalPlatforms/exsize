import secrets

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from exsize.database import get_db
from exsize.deps import get_current_user, resolve_api_token_user
from exsize.models import ApiToken, CryploTransfer, User
from exsize.security import hash_password, verify_password

router = APIRouter(prefix="/api/cryplo", tags=["cryplo"])

bearer_scheme = HTTPBearer()


class TokenResponse(BaseModel):
    id: int
    token: str


@router.post("/tokens", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def generate_token(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    raw_token = f"exs_{secrets.token_hex(32)}"
    api_token = ApiToken(
        token_hash=hash_password(raw_token),
        user_id=user.id,
    )
    db.add(api_token)
    db.commit()
    db.refresh(api_token)
    return TokenResponse(id=api_token.id, token=raw_token)


class TokenListItem(BaseModel):
    id: int
    is_active: bool
    created_at: datetime | None


@router.get("/tokens", response_model=list[TokenListItem])
def list_tokens(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tokens = db.query(ApiToken).filter(ApiToken.user_id == user.id).all()
    return [
        TokenListItem(id=t.id, is_active=t.revoked_at is None, created_at=t.created_at)
        for t in tokens
    ]


@router.patch("/tokens/{token_id}/revoke", response_model=TokenListItem)
def revoke_token(token_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    api_token = db.query(ApiToken).filter(
        ApiToken.id == token_id, ApiToken.user_id == user.id,
    ).first()
    if not api_token:
        raise HTTPException(status_code=404, detail="Token not found")
    api_token.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return TokenListItem(id=api_token.id, is_active=False, created_at=api_token.created_at)


class VerifyRequest(BaseModel):
    token: str


class VerifyResponse(BaseModel):
    valid: bool
    user_id: int | None = None
    email: str | None = None
    username: str | None = None
    error: str | None = None


@router.post("/verify-token", response_model=VerifyResponse)
def verify_token(body: VerifyRequest, db: Session = Depends(get_db)):
    for api_token in db.query(ApiToken).filter(ApiToken.revoked_at.is_(None)).all():
        if verify_password(body.token, api_token.token_hash):
            user = db.query(User).filter(User.id == api_token.user_id).first()
            return VerifyResponse(
                valid=True,
                user_id=user.id,
                email=user.email,
                username=user.nickname,
            )
    return JSONResponse(status_code=401, content={"valid": False, "error": "invalid_token"})


def _get_user_from_api_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    user = resolve_api_token_user(db, credentials.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API token")
    return user


class BalanceResponse(BaseModel):
    excoin_balance: int
    user_id: int


@router.get("/balance", response_model=BalanceResponse)
def get_balance(user: User = Depends(_get_user_from_api_token)):
    return BalanceResponse(excoin_balance=user.exbucks_balance, user_id=user.id)


class WithdrawRequest(BaseModel):
    amount_usd: float
    cryplo_user_id: str


class WithdrawResponse(BaseModel):
    success: bool
    excoin_amount: float
    exsize_user_id: int
    transfer_id: int
    new_excoin_balance: float
    weekly_remaining_usd: float


WEEKLY_LIMIT_USD = 60


@router.post("/withdraw", response_model=WithdrawResponse)
def withdraw(
    body: WithdrawRequest,
    user: User = Depends(_get_user_from_api_token),
    db: Session = Depends(get_db),
):
    excoin_amount = body.amount_usd / 2

    from sqlalchemy import func as sa_func
    week_start = datetime.now(timezone.utc) - timedelta(days=datetime.now(timezone.utc).weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    weekly_used = db.query(sa_func.coalesce(sa_func.sum(CryploTransfer.amount_usd), 0)).filter(
        CryploTransfer.exsize_user_id == user.id,
        CryploTransfer.type == "withdraw",
        CryploTransfer.created_at >= week_start,
    ).scalar()

    if weekly_used + body.amount_usd > WEEKLY_LIMIT_USD:
        return JSONResponse(status_code=429, content={
            "success": False,
            "error": "weekly_limit_exceeded",
            "weekly_used_usd": weekly_used,
            "weekly_limit_usd": WEEKLY_LIMIT_USD,
            "remaining_usd": max(0, WEEKLY_LIMIT_USD - weekly_used),
        })

    user.exbucks_balance = int(user.exbucks_balance + excoin_amount)
    transfer = CryploTransfer(
        exsize_user_id=user.id,
        type="withdraw",
        amount_usd=body.amount_usd,
        excoin_amount=excoin_amount,
        status="completed",
        completed_at=datetime.now(timezone.utc),
    )
    db.add(transfer)
    db.commit()
    db.refresh(transfer)
    db.refresh(user)

    return WithdrawResponse(
        success=True,
        excoin_amount=excoin_amount,
        exsize_user_id=user.id,
        transfer_id=transfer.id,
        new_excoin_balance=user.exbucks_balance,
        weekly_remaining_usd=WEEKLY_LIMIT_USD - weekly_used - body.amount_usd,
    )


class DepositRequest(BaseModel):
    amount_usd: float
    cryplo_user_id: str


class DepositResponse(BaseModel):
    success: bool
    excoin_amount: float
    exsize_user_id: int
    transfer_id: int
    new_excoin_balance: float


@router.post("/deposit", response_model=DepositResponse)
def deposit(
    body: DepositRequest,
    user: User = Depends(_get_user_from_api_token),
    db: Session = Depends(get_db),
):
    excoin_amount = body.amount_usd / 2
    if user.exbucks_balance < excoin_amount:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "insufficient_funds", "current_balance": user.exbucks_balance},
        )
    user.exbucks_balance = int(user.exbucks_balance - excoin_amount)
    transfer = CryploTransfer(
        exsize_user_id=user.id,
        type="deposit",
        amount_usd=body.amount_usd,
        excoin_amount=excoin_amount,
        status="completed",
        completed_at=datetime.now(timezone.utc),
    )
    db.add(transfer)
    db.commit()
    db.refresh(transfer)
    db.refresh(user)
    return DepositResponse(
        success=True,
        excoin_amount=excoin_amount,
        exsize_user_id=user.id,
        transfer_id=transfer.id,
        new_excoin_balance=user.exbucks_balance,
    )
