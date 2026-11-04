"""Model registry. Import every module's models here so Alembic autogenerate sees them."""

from app.db.base import Base

__all__ = ["Base"]
