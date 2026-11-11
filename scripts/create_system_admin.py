from getpass import getpass
from pathlib import Path
import re
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from backend.app.core.security import hash_password
from backend.app.database.connection import SessionLocal
from backend.app.database.models.identity import User


def required_input(label: str) -> str:
    value = input(f"{label}: ").strip()
    if not value:
        raise ValueError(f"{label} is required.")
    return value


def main() -> None:
    display_name = required_input("Administrator name")
    email = required_input("Administrator email").lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise ValueError("Enter a valid email address.")

    password = getpass("Password (at least 12 characters): ")
    confirmation = getpass("Confirm password: ")
    if len(password) < 12:
        raise ValueError("The password must contain at least 12 characters.")
    if password != confirmation:
        raise ValueError("Passwords do not match.")

    with SessionLocal() as db:
        has_existing_admin = db.scalar(
            select(User.id)
            .where(User.is_system_admin.is_(True), User.is_active.is_(True))
            .limit(1)
        )
        if has_existing_admin is None:
            raise RuntimeError(
                "No active system administrator exists. Use bootstrap_admin.py first."
            )

        existing_user = db.scalar(
            select(User.id).where(User.email == email)
        )
        if existing_user is not None:
            raise RuntimeError("A user with this email already exists.")

        db.add(
            User(
                email=email,
                display_name=display_name,
                password_hash=hash_password(password),
                is_active=True,
                is_system_admin=True,
            )
        )
        db.commit()

    print(f"Created system administrator account for {email}.")


if __name__ == "__main__":
    main()