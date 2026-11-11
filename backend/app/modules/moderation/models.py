"""Indexes that serve the moderation pages. Defined here, on other modules' tables, so the
moderation feature stays in its own files."""

from sqlalchemy import Index, text

from app.modules.users.models import User
from app.modules.videos.models import Video

# The hidden videos list, newest first. Hidden videos are few: a small partial index.
Index("ix_videos_hidden_id", Video.id, postgresql_where=text("is_hidden"))
# Banned and terminated accounts: the admins' list, and the terminated channels that public
# lists leave out (videos.repository.NOT_RESTRICTED). Few rows.
Index("ix_users_restricted_id", User.id, postgresql_where=text("status <> 'active'"))
