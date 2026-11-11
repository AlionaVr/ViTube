"""DB rules for subscriptions: they hold whatever the app does."""

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.modules.channels.models import Subscription
from app.modules.users.models import User
from tests.videos.factories import make_user


async def test_self_subscription_is_refused(db: AsyncSession) -> None:
    anna = await make_user(db, "anna")
    db.add(Subscription(subscriber_id=anna.id, channel_id=anna.id))

    with pytest.raises(IntegrityError, match="ck_subscriptions_not_self"):
        await db.commit()


async def test_second_subscription_is_refused(db: AsyncSession) -> None:
    anna, bob = await make_user(db, "anna"), await make_user(db, "bob")
    db.add(Subscription(subscriber_id=bob.id, channel_id=anna.id))
    await db.commit()
    db.add(Subscription(subscriber_id=bob.id, channel_id=anna.id))

    with pytest.raises(IntegrityError, match="pk_subscriptions"):
        await db.commit()


async def test_subscriber_count_never_goes_below_zero(db: AsyncSession) -> None:
    anna = await make_user(db, "anna")

    with pytest.raises(IntegrityError, match="ck_users_subscriber_count_not_negative"):
        await db.execute(update(User).where(User.id == anna.id).values(subscriber_count=-1))


async def test_deleting_a_user_deletes_their_subscriptions(
    db: AsyncSession, admin_engine: AsyncEngine
) -> None:
    anna, bob, carl = [await make_user(db, name) for name in ("anna", "bob", "carl")]
    db.add_all(
        [
            Subscription(subscriber_id=bob.id, channel_id=anna.id),
            Subscription(subscriber_id=anna.id, channel_id=carl.id),
            Subscription(subscriber_id=bob.id, channel_id=carl.id),
        ]
    )
    await db.commit()

    # The superuser: no feature deletes users yet, and the app role keeps DML for later.
    async with admin_engine.begin() as conn:
        await conn.execute(delete(User).where(User.id == anna.id))

    rows = await db.scalar(select(func.count()).select_from(Subscription))
    assert rows == 1  # only bob → carl is left
