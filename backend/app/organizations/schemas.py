from pydantic import BaseModel, ConfigDict, Field


class OrganizationListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    role: str


class OrganizationDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    role: str


class OrganizationUpdateRequest(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=150,
    )