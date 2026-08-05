from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from exsize.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    exbucks: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="assigned")
    assigned_to: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    family_id: Mapped[int] = mapped_column(Integer, ForeignKey("families.id"), nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    day_of_week: Mapped[str | None] = mapped_column(String, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String, nullable=True)


class Family(Base):
    __tablename__ = "families"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pin: Mapped[str] = mapped_column(String(6), unique=True, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False, default="en")
    family_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("families.id"), nullable=True)
    exbucks_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_completion_date: Mapped[str | None] = mapped_column(String, nullable=True)
    date_of_birth: Mapped[str | None] = mapped_column(String, nullable=True)
    nickname: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    nickname_changes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    equipped_icon_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("avatar_items.id"), nullable=True)
    equipped_background_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("avatar_items.id"), nullable=True)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    task_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("tasks.id"), nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime, nullable=False, server_default=func.now())



class DeletionRequest(Base):
    __tablename__ = "deletion_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    child_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    family_id: Mapped[int] = mapped_column(Integer, ForeignKey("families.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    created_at: Mapped[str] = mapped_column(DateTime, nullable=False, server_default=func.now())


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, nullable=False)


class AvatarItem(Base):
    __tablename__ = "avatar_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String, nullable=False)  # "icon" or "background"
    value: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active_in_shop: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[str] = mapped_column(DateTime, nullable=False, server_default=func.now())


class UserInventory(Base):
    __tablename__ = "user_inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    avatar_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("avatar_items.id"), nullable=False)
    purchased_at: Mapped[str] = mapped_column(DateTime, nullable=False, server_default=func.now())


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(Integer, ForeignKey("families.id"), unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    current_period_end: Mapped[str | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime, nullable=False, server_default=func.now())


class ApiToken(Base):
    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime, nullable=False, server_default=func.now())
    revoked_at: Mapped[str | None] = mapped_column(DateTime, nullable=True)


class CryploTransfer(Base):
    __tablename__ = "cryplo_transfers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exsize_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)  # "deposit" or "withdraw"
    amount_usd: Mapped[float] = mapped_column(Float, nullable=False)
    excoin_amount: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="completed")
    created_at: Mapped[str] = mapped_column(DateTime, nullable=False, server_default=func.now())
    completed_at: Mapped[str | None] = mapped_column(DateTime, nullable=True)


class TodoList(Base):
    __tablename__ = "todo_lists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime, nullable=False, server_default=func.now())


class TodoItem(Base):
    __tablename__ = "todo_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    list_id: Mapped[int] = mapped_column(Integer, ForeignKey("todo_lists.id"), nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    recurrence: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime, nullable=False, server_default=func.now())
