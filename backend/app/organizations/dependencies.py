from typing import Annotated

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.database import get_db
from app.models.membership import Membership, MembershipRole
from app.models.user import User


def get_current_membership(
    organization_id: Annotated[str, Path()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Membership:
    membership = db.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == current_user.id,
        )
    )

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    return membership


def require_organization_admin(
    membership: Annotated[
        Membership,
        Depends(get_current_membership),
    ],
) -> Membership:
    allowed_roles = {
        MembershipRole.owner,
        MembershipRole.admin,
    }

    if membership.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage this organization.",
        )

    return membership


def require_organization_owner(
    membership: Annotated[
        Membership,
        Depends(get_current_membership),
    ],
) -> Membership:
    if membership.role != MembershipRole.owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an organization owner can perform this action.",
        )

    return membership