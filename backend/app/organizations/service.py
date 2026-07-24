import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.membership import Membership
from app.models.organization import Organization


class OrganizationUpdateError(Exception):
    """Raised when an organization cannot be updated."""


def create_slug(value: str) -> str:
    slug = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")

    if not slug:
        raise OrganizationUpdateError(
            "Organization name must contain letters or numbers."
        )

    return slug[:150]


def generate_unique_slug(
    db: Session,
    organization_name: str,
    current_organization_id: str,
) -> str:
    base_slug = create_slug(organization_name)
    candidate_slug = base_slug
    counter = 2

    while db.scalar(
        select(Organization.id).where(
            Organization.slug == candidate_slug,
            Organization.id != current_organization_id,
        )
    ):
        suffix = f"-{counter}"
        candidate_slug = (
            f"{base_slug[:150 - len(suffix)]}{suffix}"
        )
        counter += 1

    return candidate_slug


def list_user_organizations(
    db: Session,
    user_id: str,
) -> list[Membership]:
    statement = (
        select(Membership)
        .where(Membership.user_id == user_id)
        .order_by(Membership.created_at.asc())
    )

    return list(db.scalars(statement).all())


def update_organization(
    db: Session,
    organization: Organization,
    new_name: str,
) -> Organization:
    cleaned_name = new_name.strip()

    if not cleaned_name:
        raise OrganizationUpdateError(
            "Organization name cannot be empty."
        )

    organization.name = cleaned_name
    organization.slug = generate_unique_slug(
        db=db,
        organization_name=cleaned_name,
        current_organization_id=organization.id,
    )

    try:
        db.commit()
        db.refresh(organization)

    except IntegrityError as exc:
        db.rollback()

        raise OrganizationUpdateError(
            "The organization could not be updated."
        ) from exc

    except Exception:
        db.rollback()
        raise

    return organization