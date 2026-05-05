"""Run-once bootstrap: ensures the admin user exists.

Reads ADMIN_USERNAME / ADMIN_PASSWORD from environment. Idempotent:
- creates the admin if missing
- updates the password hash if the env password no longer verifies
"""
from sqlalchemy import select

from app.auth import hash_password, verify_password
from app.config import settings
from app.db import SessionLocal
from app.models import AdminUser


def main() -> None:
    with SessionLocal() as db:
        admin = db.scalars(
            select(AdminUser).where(AdminUser.username == settings.admin_username)
        ).first()
        if admin is None:
            admin = AdminUser(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
            )
            db.add(admin)
            db.commit()
            print(f"[bootstrap] created admin '{settings.admin_username}'")
        elif not verify_password(settings.admin_password, admin.password_hash):
            admin.password_hash = hash_password(settings.admin_password)
            db.commit()
            print(f"[bootstrap] updated admin '{settings.admin_username}' password")
        else:
            print(f"[bootstrap] admin '{settings.admin_username}' OK")


if __name__ == "__main__":
    main()
