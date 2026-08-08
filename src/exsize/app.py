import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from sqlalchemy.orm import Session

from exsize.database import Base, engine, SessionLocal
from exsize.models import AppSetting, AvatarItem, User
from exsize.routers import account, admin_settings, auth, avatar, cryplo, dashboard, exbucks, family, gamification, leaderboard, profile, push, settings, subscription, tasks, todo
from exsize.security import hash_password


def _seed_app_settings(db: Session) -> None:
    if not db.query(AppSetting).filter(AppSetting.key == "max_exbucks_per_task").first():
        db.add(AppSetting(key="max_exbucks_per_task", value="50"))
        db.commit()


def _seed_admin(db: Session) -> None:
    if not db.query(User).filter(User.role == "admin").first():
        db.add(User(
            email="admin@exsize.app",
            password_hash=hash_password("unused"),
            role="admin",
            language="en",
        ))
        db.commit()


DEFAULT_ICONS = [
    {"value": "⭐", "label": "Star", "price": 10},
    {"value": "🎮", "label": "Gamepad", "price": 20},
    {"value": "🏆", "label": "Trophy", "price": 30},
    {"value": "🎯", "label": "Bullseye", "price": 40},
    {"value": "🔥", "label": "Fire", "price": 50},
    {"value": "💎", "label": "Diamond", "price": 75},
    {"value": "🦄", "label": "Unicorn", "price": 100},
]

DEFAULT_BACKGROUNDS = [
    {"value": "#4FC3F7", "label": "Sky Blue", "price": 10},
    {"value": "#81C784", "label": "Mint Green", "price": 20},
    {"value": "#FFB74D", "label": "Warm Orange", "price": 30},
    {"value": "#E57373", "label": "Coral Red", "price": 40},
    {"value": "#BA68C8", "label": "Purple", "price": 50},
    {"value": "linear-gradient(135deg, #667eea, #764ba2)", "label": "Galaxy", "price": 75},
    {"value": "linear-gradient(135deg, #f093fb, #f5576c)", "label": "Sunset", "price": 100},
]

FREE_DEFAULT_ICON = {"value": "👤", "label": "Default User", "price": 0}
FREE_DEFAULT_BACKGROUND = {"value": "#F48FB1", "label": "Pink", "price": 0}


def _seed_avatar_items(db: Session) -> None:
    if db.query(AvatarItem).first():
        return
    for icon in DEFAULT_ICONS:
        db.add(AvatarItem(type="icon", is_default=True, active_in_shop=True, **icon))
    db.add(AvatarItem(type="icon", is_default=True, active_in_shop=True, **FREE_DEFAULT_ICON))
    for bg in DEFAULT_BACKGROUNDS:
        db.add(AvatarItem(type="background", is_default=True, active_in_shop=True, **bg))
    db.add(AvatarItem(type="background", is_default=True, active_in_shop=True, **FREE_DEFAULT_BACKGROUND))
    db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _seed_admin(db)
        _seed_app_settings(db)
        _seed_avatar_items(db)
    finally:
        db.close()
    yield


app = FastAPI(title="ExSize", lifespan=lifespan)

cors_origins = os.environ.get("CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(account.router)
app.include_router(cryplo.router)
app.include_router(admin_settings.router)
app.include_router(auth.router)
app.include_router(avatar.router)
app.include_router(dashboard.router)
app.include_router(exbucks.router)
app.include_router(family.router)
app.include_router(gamification.router)
app.include_router(leaderboard.router)
app.include_router(profile.router)
app.include_router(settings.router)
app.include_router(subscription.router)
app.include_router(push.router)
app.include_router(tasks.router)
app.include_router(todo.router)
