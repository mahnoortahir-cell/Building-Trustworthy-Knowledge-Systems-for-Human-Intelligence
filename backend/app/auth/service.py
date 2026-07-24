import re
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.schemas import RegisterRequest
from app.auth.security import (create_access_token, hash_password, verify_password,)
from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.models.user import User


class EmailAlreadyRegisteredError(Exception):
    """Raised when an account already exists for the supplied email."""


class RegistrationError(Exception):
    """Raised when registration cannot be completed."""

class InvalidCredentialsError(Exception):
    """Raised when the email or password is incorrect."""


class InactiveUserError(Exception):
    """Raised when an inactive user attempts to log in."""    


def create_slug(value: str) -> str:
    """
    Convert an organization name into a URL-safe slug.

    Example:
        "Noor Research Lab" -> "noor-research-lab"
    """
    slug = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")

    if not slug:
        slug = f"organization-{uuid4().hex[:8]}"

    return slug[:150]


def generate_unique_organization_slug(
    db: Session,
    organization_name: str,
) -> str:
    base_slug = create_slug(organization_name)
    candidate_slug = base_slug
    counter = 2

    while db.scalar(
        select(Organization.id).where(
            Organization.slug == candidate_slug
        )
    ):
        suffix = f"-{counter}"
        candidate_slug = f"{base_slug[:150 - len(suffix)]}{suffix}"
        counter += 1

    return candidate_slug


def register_user(
    db: Session,
    registration_data: RegisterRequest,
) -> tuple[User, Organization, Membership, str]:
    normalized_email = registration_data.email.lower().strip()

    existing_user = db.scalar(
        select(User).where(User.email == normalized_email)
    )

    if existing_user is not None:
        raise EmailAlreadyRegisteredError(
            "An account with this email already exists."
        )

    organization_slug = generate_unique_organization_slug(
        db=db,
        organization_name=registration_data.organization_name,
    )

    organization = Organization(
        name=registration_data.organization_name,
        slug=organization_slug,
    )

    user = User(
        full_name=registration_data.full_name,
        email=normalized_email,
        hashed_password=hash_password(registration_data.password),
        is_active=True,
    )

    membership = Membership(
        user=user,
        organization=organization,
        role=MembershipRole.owner,
    )

    try:
        db.add_all([organization, user, membership])
        db.commit()

        db.refresh(user)
        db.refresh(organization)
        db.refresh(membership)

    except IntegrityError as exc:
        db.rollback()

        raise RegistrationError(
            "Registration could not be completed because some information "
            "already exists."
        ) from exc

    except Exception:
        db.rollback()
        raise

    access_token = create_access_token(subject=user.id)

    return user, organization, membership, access_token

def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> tuple[User, str]:
    normalized_email = email.strip().lower()

    user = db.scalar(
        select(User).where(User.email == normalized_email)
    )

    # Use the same error for an unknown email and a wrong password.
    # This avoids revealing whether a particular account exists.
    if user is None or not verify_password(
        plain_password=password,
        hashed_password=user.hashed_password,
    ):
        raise InvalidCredentialsError(
            "Incorrect email or password."
        )

    if not user.is_active:
        raise InactiveUserError(
            "This account is inactive."
        )

    access_token = create_access_token(subject=user.id)

    return user, access_token