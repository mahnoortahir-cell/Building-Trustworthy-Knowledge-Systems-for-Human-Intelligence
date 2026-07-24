from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.database import get_db
from app.models.membership import Membership
from app.models.user import User
from app.organizations.dependencies import (
    get_current_membership,
    require_organization_admin,
)
from app.organizations.schemas import (
    OrganizationDetailResponse,
    OrganizationListItem,
    OrganizationUpdateRequest,
)
from app.organizations.service import (
    OrganizationUpdateError,
    list_user_organizations,
    update_organization,
)


router = APIRouter(
    prefix="/organizations",
    tags=["Organizations"],
)


@router.get(
    "",
    response_model=list[OrganizationListItem],
    status_code=status.HTTP_200_OK,
)
def get_my_organizations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[OrganizationListItem]:
    memberships = list_user_organizations(
        db=db,
        user_id=current_user.id,
    )

    return [
        OrganizationListItem(
            id=membership.organization.id,
            name=membership.organization.name,
            slug=membership.organization.slug,
            role=membership.role.value,
        )
        for membership in memberships
    ]


@router.get(
    "/{organization_id}",
    response_model=OrganizationDetailResponse,
    status_code=status.HTTP_200_OK,
)
def get_organization(
    membership: Annotated[
        Membership,
        Depends(get_current_membership),
    ],
) -> OrganizationDetailResponse:
    organization = membership.organization

    return OrganizationDetailResponse(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        role=membership.role.value,
    )


@router.patch(
    "/{organization_id}",
    response_model=OrganizationDetailResponse,
    status_code=status.HTTP_200_OK,
)
def update_organization_details(
    update_data: OrganizationUpdateRequest,
    membership: Annotated[
        Membership,
        Depends(require_organization_admin),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> OrganizationDetailResponse:
    try:
        organization = update_organization(
            db=db,
            organization=membership.organization,
            new_name=update_data.name,
        )

    except OrganizationUpdateError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return OrganizationDetailResponse(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        role=membership.role.value,
    )