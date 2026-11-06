"""Model registry. Import every module's models here so Alembic autogenerate sees them."""

from app.db.base import Base
from app.modules.users.models import User

__all__ = ["Base", "User"]
