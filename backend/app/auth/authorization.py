from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.models.membership import MembershipRole
from app.models.user import User


def require_role(
    allowed_roles: set[MembershipRole],
) -> Callable[..., User]:
    def role_dependency(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        user_roles = {
            membership.role
            for membership in current_user.memberships
        }

        if not user_roles.intersection(allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )

        return current_user

    return role_dependency


require_owner = require_role({
    MembershipRole.owner,
})

require_admin = require_role({
    MembershipRole.owner,
    MembershipRole.admin,
})

require_member = require_role({
    MembershipRole.owner,
    MembershipRole.admin,
    MembershipRole.member,
})