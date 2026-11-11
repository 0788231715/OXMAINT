from getpass import getpass
from pathlib import Path
import re
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from backend.app.core.security import hash_password
from backend.app.database.connection import SessionLocal
from backend.app.database.models.identity import (
    Role,
    User,
    UserRoleAssignment,
    UserSiteAccess,
)
from backend.app.database.models.organization import Organization, Site


MANAGER_ROLE_CODE = "maintenance_manager"


def required_input(label: str) -> str:
    value = input(f"{label}: ").strip()
    if not value:
        raise ValueError(f"{label} is required.")
    return value


def main() -> None:
    print("Create the first OxMaint organization and maintenance manager.")
    organization_name = required_input("Organization name")
    organization_code = required_input("Organization code").upper()
    site_name = required_input("Initial site name")
    site_code = required_input("Initial site code").upper()
    display_name = required_input("Manager name")
    email = required_input("Manager email").lower()

    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise ValueError("Enter a valid email address.")

    password = getpass("Manager password (at least 12 characters): ")
    confirmation = getpass("Confirm password: ")
    if len(password) < 12:
        raise ValueError("The password must contain at least 12 characters.")
    if password != confirmation:
        raise ValueError("Passwords do not match.")

    with SessionLocal() as db:
        if db.scalar(select(User.id).limit(1)) is not None:
            raise RuntimeError(
                "Bootstrap is only allowed before the first user exists."
            )

        role = db.scalar(
            select(Role).where(
                Role.code == MANAGER_ROLE_CODE,
                Role.is_active.is_(True),
            )
        )
        if role is None:
            raise RuntimeError(
                "The maintenance manager role is missing. Run database migrations first."
            )

        organization = Organization(
            name=organization_name,
            code=organization_code,
        )
        user = User(
            email=email,
            display_name=display_name,
            password_hash=hash_password(password),
            is_active=True,
            is_system_admin=True,
        )
        db.add_all([organization, user])
        db.flush()

        site = Site(
            organization_id=organization.id,
            name=site_name,
            code=site_code,
        )
        db.add(site)
        db.flush()

        db.add_all([
            UserRoleAssignment(
                user_id=user.id,
                role_id=role.id,
                organization_id=organization.id,
                granted_by=user.id,
            ),
            UserSiteAccess(
                user_id=user.id,
                site_id=site.id,
                granted_by=user.id,
            ),
        ])
        db.commit()

    print(f"Created system administrator account for {email}.")
    print(f"Organization: {organization_name} ({organization_code})")
    print(f"Initial site: {site_name} ({site_code})")


if __name__ == "__main__":
    main()