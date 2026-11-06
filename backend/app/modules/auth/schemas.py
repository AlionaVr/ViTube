from typing import Annotated

from email_validator import EmailNotValidError, validate_email
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, WithJsonSchema

from app.modules.users.models import Role


def _ascii_email(value: str) -> str:
    # SMTPUTF8 off: an ASCII local part, and the domain comes back as punycode. All-ASCII
    # addresses lowercase the same in Python (rate limit keys) and Postgres (citext lookups).
    try:
        info = validate_email(value, check_deliverability=False, allow_smtputf8=False)
    except EmailNotValidError as error:
        raise ValueError(str(error)) from None
    if info.ascii_email is None:  # only possible with SMTPUTF8 on
        raise ValueError("The email address must be ASCII")
    return info.ascii_email


Email = Annotated[
    str, AfterValidator(_ascii_email), WithJsonSchema({"type": "string", "format": "email"})
]


class Credentials(BaseModel):
    email: Email
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    handle: str
    email: str
    role: Role
