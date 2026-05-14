import uuid

import pytest
from fastapi import HTTPException

from app.dependencies import _verify_slug
from app.models.user import User


def _user(slug):
    return User(
        id=uuid.uuid4(), email=f"{slug}@x.z", slug=slug, role="USER", is_active=True,
    )


def test_matching_slug_returns_user():
    u = _user("pin0513")
    assert _verify_slug("pin0513", u) is u


def test_mismatched_slug_raises_404():
    u = _user("pin0513")
    with pytest.raises(HTTPException) as ei:
        _verify_slug("someone-else", u)
    assert ei.value.status_code == 404


def test_admin_bypasses_slug_check_for_self_only():
    # Admin can still only see their own; explicit "as=" not supported in P2
    admin = _user("admin0")
    admin.role = "ADMIN"
    with pytest.raises(HTTPException) as ei:
        _verify_slug("other-slug", admin)
    assert ei.value.status_code == 404
