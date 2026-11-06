from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.users.models import Role


class Credentials(BaseModel):
    email: EmailStr  # email-validator also caps the length (254)
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    handle: str
    email: str
    role: Role
