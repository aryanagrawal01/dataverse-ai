"""Auth DTOs crossing the service boundary."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str | None
    last_login_at: datetime | None


class AuthResult(BaseModel):
    user: UserDTO
    token: str
