import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import Role, User


def new_user(email: str = "anna@example.com", handle: str = "user-k3j9x2m1") -> User:
    return User(email=email, handle=handle, password_hash="hash")


async def test_db_fills_id_role_and_created_at(db: AsyncSession) -> None:
    user = new_user()
    db.add(user)
    await db.commit()

    assert user.id.version == 7
    assert user.role is Role.USER
    assert user.created_at is not None


async def test_email_is_unique_ignoring_case(db: AsyncSession) -> None:
    db.add(new_user(email="anna@example.com", handle="user-aaaaaaaa"))
    await db.commit()
    db.add(new_user(email="Anna@Example.COM", handle="user-bbbbbbbb"))

    with pytest.raises(IntegrityError, match="uq_users_email"):
        await db.commit()


async def test_handle_is_unique(db: AsyncSession) -> None:
    db.add(new_user(email="anna@example.com"))
    await db.commit()
    db.add(new_user(email="bob@example.com"))

    with pytest.raises(IntegrityError, match="uq_users_handle"):
        await db.commit()


@pytest.mark.parametrize("handle", ["ab", "x" * 31, "User-k3j9", "user k3j9", "@user"])
async def test_handle_format_is_checked(db: AsyncSession, handle: str) -> None:
    db.add(new_user(handle=handle))

    with pytest.raises(IntegrityError, match="ck_users_handle_format"):
        await db.commit()


@pytest.mark.parametrize("handle", ["abc", "x" * 30, "a.b_c-d"])
async def test_valid_handles_are_accepted(db: AsyncSession, handle: str) -> None:
    db.add(new_user(handle=handle))
    await db.commit()


# alembic check doesn't compare CHECK constraints: this catches a new role without a migration.
@pytest.mark.parametrize("role", list(Role))
async def test_db_accepts_every_role(db: AsyncSession, role: Role) -> None:
    db.add(User(email="anna@example.com", handle="user-k3j9x2m1", password_hash="hash", role=role))
    await db.commit()


async def test_unknown_role_is_rejected(db: AsyncSession) -> None:
    # Raw SQL: the Python enum would reject the value before it reaches the DB.
    insert = text(
        "INSERT INTO users (email, handle, password_hash, role)"
        " VALUES ('anna@example.com', 'user-k3j9x2m1', 'hash', 'owner')"
    )

    with pytest.raises(IntegrityError, match="ck_users_role"):
        await db.execute(insert)
