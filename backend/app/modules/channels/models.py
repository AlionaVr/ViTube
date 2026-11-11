"""Subscriptions. A channel is a user (its handle is the address), so both sides point at users."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Subscription(Base):
    """One row per subscriber and channel: the key makes a second subscription impossible."""

    __tablename__ = "subscriptions"
    __table_args__ = (CheckConstraint("subscriber_id <> channel_id", name="not_self"),)

    # Key order: "my subscriptions" reads by subscriber.
    subscriber_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # Indexed: cascades when a channel's user is deleted.
    channel_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
