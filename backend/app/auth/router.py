from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.schemas import RegisterRequest, RegisterResponse
from app.auth.service import (
    EmailAlreadyRegisteredError,
    RegistrationError,
    register_user,
)
from app.core.database import get_db


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