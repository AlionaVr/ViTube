"""Users. A user is also a channel: the handle is its public address, /@handle."""

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Enum, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


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


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        # Cast to text: on citext, ~ ignores case.
        CheckConstraint(r"handle::text ~ '^[a-z0-9._-]{3,30}$'", name="handle_format"),
        CheckConstraint("subscriber_count >= 0", name="subscriber_count_not_negative"),
    )

    # uuidv7(): time-ordered (index-friendly) and not guessable like 1, 2, 3.
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    email: Mapped[str] = mapped_column(CITEXT, unique=True)
    handle: Mapped[str] = mapped_column(CITEXT, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
