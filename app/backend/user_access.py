from __future__ import annotations

from .config import settings
from .models import User
from .schemas import UserAdminOut, UserOut


SUPER_USER_ROLE = "super_user"
LEGACY_SUPER_USER_ROLE = "super" + "_admin"
VIEWER_ROLE = "viewer"
ADMIN_ROLES = {"admin", SUPER_USER_ROLE, LEGACY_SUPER_USER_ROLE}
EDITOR_ROLES = {"leader", *ADMIN_ROLES}


def is_super_user(user: User) -> bool:
    role = (user.role or "").strip().lower()
    if role in {SUPER_USER_ROLE, LEGACY_SUPER_USER_ROLE}:
        return True
    if role != "admin":
        return False
    return user.username.strip().lower() in settings.super_user_usernames


def user_needs_password_setup(user: User) -> bool:
    return user.password_hash is None or bool(user.must_change_password)


def is_viewer(user: User) -> bool:
    return (user.role or "").strip().lower() == VIEWER_ROLE


def can_edit_planning(user: User) -> bool:
    return (user.role or "").strip().lower() in EDITOR_ROLES


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        must_change_password=user_needs_password_setup(user),
        is_super_user=is_super_user(user),
    )


def user_admin_out(user: User) -> UserAdminOut:
    return UserAdminOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        must_change_password=user_needs_password_setup(user),
        created_at=user.created_at,
        is_super_user=is_super_user(user),
    )
