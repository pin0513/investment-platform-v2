"""
Idempotent DB initialization:
  1. Ensure pgcrypto extension
  2. Run alembic upgrade head
  3. Seed industries
  4. Create first admin user from FIRST_ADMIN_EMAIL
"""

from __future__ import annotations

import logging
import subprocess
import sys
import uuid
from pathlib import Path

# Resolve the alembic binary from the same Python installation running this script.
_ALEMBIC = str(Path(sys.executable).parent / "alembic")

from sqlalchemy import text

from app.config import get_settings
from app.db import session_scope
from app.models.allowlisted_email import AllowlistedEmail
from app.models.user import User

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("init_db")


def run_alembic() -> None:
    log.info("Running alembic upgrade head...")
    result = subprocess.run(
        [_ALEMBIC, "upgrade", "head"], capture_output=True, text=True
    )
    if result.returncode != 0:
        log.error("alembic failed: %s", result.stderr)
        sys.exit(1)
    log.info("alembic OK")


def run_seed_industries() -> None:
    seed_file = Path(__file__).parent / "seed_industries.sql"
    sql = seed_file.read_text()
    with session_scope() as s:
        s.execute(text(sql))
    log.info("Industries seed OK")


def slugify_email(email: str) -> str:
    return email.split("@", 1)[0].lower().replace(".", "_").replace("+", "_")


def ensure_first_admin() -> None:
    settings = get_settings()
    email = settings.first_admin_email
    if not email:
        log.warning("FIRST_ADMIN_EMAIL not set; skipping admin creation")
        return

    with session_scope() as s:
        existing = s.query(User).filter(User.email == email).one_or_none()
        if existing:
            log.info("Admin user %s already exists", email)
            return

        slug = slugify_email(email)
        user = User(
            id=uuid.uuid4(),
            email=email,
            slug=slug,
            display_name=email.split("@")[0],
            role="ADMIN",
            is_active=True,
            base_currency="TWD",
            timezone="Asia/Taipei",
        )
        s.add(user)
        s.flush()

        # Add to allowlist
        s.merge(AllowlistedEmail(email=email, invited_by=user.id, notes="auto-seeded admin"))

        log.info("Created admin user %s (slug=%s)", email, slug)


def main() -> None:
    log.info("DB URL: %s", get_settings().db_url[:40] + "...")
    run_alembic()
    run_seed_industries()
    ensure_first_admin()
    log.info("init_db complete")


if __name__ == "__main__":
    main()
