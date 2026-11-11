"""Column types shared by models."""

import enum

from sqlalchemy import Enum


def str_enum(enum_class: type[enum.StrEnum], name: str) -> Enum:
    # varchar + CHECK, not a Postgres enum: adding a value is a plain migration.
    return Enum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=16,
        values_callable=lambda members: [member.value for member in members],
    )
