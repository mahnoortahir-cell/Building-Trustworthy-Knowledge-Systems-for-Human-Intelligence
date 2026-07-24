from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    organization_name: str = Field(min_length=2, max_length=150)

    @field_validator("full_name", "organization_name")
    @classmethod
    def strip_and_validate_text(cls, value: str) -> str:
        cleaned_value = value.strip()

        if not cleaned_value:
            raise ValueError("This field cannot be empty.")

        return cleaned_value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    full_name: str
    email: EmailStr
    is_active: bool


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str


class RegisterResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user: UserResponse
    organization: OrganizationResponse

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class CurrentOrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    role: str


class CurrentUserResponse(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    is_active: bool
    organizations: list[CurrentOrganizationResponse]