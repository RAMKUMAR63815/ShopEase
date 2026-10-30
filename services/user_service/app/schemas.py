from pydantic import BaseModel, ConfigDict, Field


class ProfileCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20)


class ProfileUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20)


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    auth_user_id: int
    first_name: str
    last_name: str
    phone: str | None