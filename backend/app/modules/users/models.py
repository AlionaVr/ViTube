"""Users. A user is also a channel: the handle is its public address, /@handle."""

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, Integer, Text, false, func, text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import str_enum


class Role(enum.Enum):
    """Nested roles (ADR 0009): each one has all rights of the ones before it.

    A plain Enum, not StrEnum: there `>=` compares strings ("user" > "moderator").
    """

    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"

    def at_least(self, minimum: "Role") -> bool:
        order = list(Role)  # declaration order: each role includes the ones above it
        return order.index(self) >= order.index(minimum)


class UserStatus(enum.StrEnum):
    """What an admin allowed the account (ADR 0009). A user is also a channel, so it is both."""

    ACTIVE = "active"
    BANNED = "banned"  # can't sign in or act; their videos and comments stay
    TERMINATED = "terminated"  # banned, and their videos are gone for all but moderators


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        # Cast to text: on citext, ~ ignores case.
        CheckConstraint(r"handle::text ~ '^[a-z0-9._-]{3,30}$'", name="handle_format"),
        CheckConstraint("subscriber_count >= 0", name="subscriber_count_not_negative"),
        # Admins can't be restricted (ADR 0009), so a restricted account can't become one.
        CheckConstraint("role <> 'admin' OR status = 'active'", name="admin_active"),
        # Every account has a way to sign in: a password, Google, or both (ADR 0014).
        CheckConstraint(
            "password_hash IS NOT NULL OR google_sub IS NOT NULL", name="has_credentials"
        ),
    )

    # uuidv7(): time-ordered (index-friendly) and not guessable like 1, 2, 3.
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    email: Mapped[str] = mapped_column(CITEXT, unique=True)
    handle: Mapped[str] = mapped_column(CITEXT, unique=True)
    # None for an account made with Google: it has no password to sign in with.
    password_hash: Mapped[str | None] = mapped_column(Text)
    # Google's "sub": the account's id, never reused. Not the email, which can change (ADR 0014).
    google_sub: Mapped[str | None] = mapped_column(Text, unique=True)
    # Read from the DB on every request, like the role: a ban applies to the next request.
    status: Mapped[UserStatus] = mapped_column(
        str_enum(UserStatus, "status"), server_default=UserStatus.ACTIVE.value
    )
    # Set by a ban or termination: sessions started before it never work again, also after a
    # reinstatement, whether or not the ban could delete them from Redis (ADR 0005).
    sessions_valid_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # varchar + CHECK, not a Postgres enum: adding a role is a plain migration.
    role: Mapped[Role] = mapped_column(
        Enum(
            Role,
            name="role",
            native_enum=False,
            create_constraint=True,
            length=16,
            values_callable=lambda roles: [role.value for role in roles],
        ),
        server_default=Role.USER.value,
    )
    # Updated in place (x = x + n) by subscriptions. Not indexed, so updates stay HOT.
    subscriber_count: Mapped[int] = mapped_column(Integer, server_default="0")
    # The user paused their watch history: the player's saves change nothing.
    history_paused: Mapped[bool] = mapped_column(Boolean, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
