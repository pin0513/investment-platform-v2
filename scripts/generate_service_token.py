"""
Generate a long-lived JWT for Cloud Scheduler use (run by admin).

Usage:
  python scripts/generate_service_token.py <name> [<minutes>]
"""
import sys
import uuid

from app.db import session_scope
from app.models.user import User
from app.repositories.user import UserRepository
from app.security import create_access_token


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: generate_service_token.py <name> [<minutes>]", file=sys.stderr)
        sys.exit(2)

    name = sys.argv[1]
    minutes = int(sys.argv[2]) if len(sys.argv) > 2 else 129_600  # 90 days

    email = f"service-{name.lower()}@invest.local"
    with session_scope() as s:
        users = UserRepository(s)
        user = users.get_by_email(email)
        if user is None:
            user = User(
                id=uuid.uuid4(),
                email=email,
                slug=f"svc-{name.lower()}",
                display_name=name,
                role="SERVICE",
                is_active=True,
            )
            users.create(user)
            s.commit()
            user = users.get_by_email(email)
        assert user is not None

        token = create_access_token(
            subject=str(user.id),
            email=user.email,
            role="SERVICE",
            scope="service",
            expires_in_minutes=minutes,
        )

    print(token)


if __name__ == "__main__":
    main()
