"""Report queries. No commits: the service decides when a transaction ends."""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, func, select, update
from sqlalchemy.dialects.postgresql import aggregate_order_by, array_agg, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reports.models import Report, ReportReason, ReportStatus

NOTES_PER_CASE = 3


@dataclass(frozen=True)
class OpenCase:
    """The open reports of one target."""

    video_id: UUID | None
    comment_id: UUID | None
    report_count: int
    reasons: list[ReportReason]
    notes: list[str]  # the newest report texts
    first_id: UUID  # the oldest open report: the queue's order and cursor
    last_reported_at: datetime


async def add(
    db: AsyncSession,
    *,
    reporter_id: UUID,
    reason: ReportReason,
    details: str,
    video_id: UUID | None = None,
    comment_id: UUID | None = None,
) -> None:
    """A second open report of the same target by the same user changes nothing."""
    statement = insert(Report).values(
        reporter_id=reporter_id,
        video_id=video_id,
        comment_id=comment_id,
        reason=reason,
        details=details,
    )
    await db.execute(statement.on_conflict_do_nothing())  # the partial unique indexes decide


async def list_open_cases(db: AsyncSession, *, after: UUID | None, limit: int) -> list[OpenCase]:
    """Open reports grouped by target, oldest case first.

    Each page aggregates all open reports: the queue holds only what moderators haven't
    handled yet, so it stays small (ix_reports_open_id leaves closed ones out).
    """
    first_id = array_agg(aggregate_order_by(Report.id, Report.id))[1]  # Postgres has no min(uuid)
    newest_first = aggregate_order_by(Report.details, Report.id.desc())
    notes = array_agg(newest_first).filter(Report.details != "")[1:NOTES_PER_CASE]
    query = (
        select(
            Report.video_id,
            Report.comment_id,
            func.count(),
            array_agg(Report.reason.distinct()),
            notes,
            first_id,
            func.max(Report.created_at),
        )
        .where(Report.status == ReportStatus.OPEN)
        .group_by(Report.video_id, Report.comment_id)
    )
    if after is not None:
        query = query.having(first_id > after)
    rows = await db.execute(query.order_by(first_id).limit(limit))
    return [
        OpenCase(
            video_id=video_id,
            comment_id=comment_id,
            report_count=count,
            reasons=[ReportReason(reason) for reason in reasons],
            notes=notes or [],  # NULL when every report of the target is without text
            first_id=first,
            last_reported_at=last,
        )
        for video_id, comment_id, count, reasons, notes, first, last in rows
    ]


async def resolve_open_of_video(
    db: AsyncSession, video_id: UUID, *, status: ReportStatus, resolved_by: UUID
) -> int:
    """Close the video's open reports. Returns how many were closed."""
    return await _resolve(db, Report.video_id == video_id, status, resolved_by)


async def resolve_open_of_comments(
    db: AsyncSession, comment_ids: Collection[UUID], *, status: ReportStatus, resolved_by: UUID
) -> int:
    """Close the open reports of these comments. Returns how many were closed."""
    return await _resolve(db, Report.comment_id.in_(comment_ids), status, resolved_by)


async def _resolve(
    db: AsyncSession, target: ColumnElement[bool], status: ReportStatus, resolved_by: UUID
) -> int:
    closed = await db.scalars(
        update(Report)
        .where(target, Report.status == ReportStatus.OPEN)
        .values(status=status, resolved_by=resolved_by, resolved_at=func.now())
        .returning(Report.id)
    )
    return len(closed.all())
