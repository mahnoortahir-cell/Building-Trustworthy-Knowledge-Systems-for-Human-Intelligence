from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.schemas import (
    CurrentOrganizationResponse,
    CurrentUserResponse,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from app.auth.service import (
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidCredentialsError,
    RegistrationError,
    authenticate_user,
    register_user,
)
from app.core.database import get_db
from app.models.user import User


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    registration_data: RegisterRequest,
    db: Session = Depends(get_db),
) -> RegisterResponse:
    try:
        user, organization, membership, access_token = register_user(
            db=db,
            registration_data=registration_data,
        )

    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except RegistrationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return RegisterResponse(
        access_token=access_token,
        token_type="bearer",
        role=membership.role.value,
        user=user,
        organization=organization,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
)
def login(
    form_data: Annotated[
        OAuth2PasswordRequestForm,
        Depends(),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    try:
        _, access_token = authenticate_user(
            db=db,
            email=form_data.username,
            password=form_data.password,
        )

    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    except InactiveUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
    )


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    status_code=status.HTTP_200_OK,
)
def get_my_profile(
    current_user: Annotated[User, Depends(get_current_user)],
) -> CurrentUserResponse:
    organizations = [
        CurrentOrganizationResponse(
            id=membership.organization.id,
            name=membership.organization.name,
            slug=membership.organization.slug,
            role=membership.role.value,
        )
        for membership in current_user.memberships
    ]

    return CurrentUserResponse(
        id=current_user.id,
        full_name=current_user.full_name,
        email=current_user.email,
        is_active=current_user.is_active,
        organizations=organizations,
    )