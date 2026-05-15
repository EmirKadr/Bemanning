import pytest
from fastapi import HTTPException

from app.backend.deps import require_planning_editor
from app.backend.models import User


def make_user(role: str) -> User:
    return User(id=1, username=f"{role}-user", role=role, is_active=True)


def test_viewer_cannot_edit_planning():
    with pytest.raises(HTTPException) as exc_info:
        require_planning_editor(make_user("viewer"))

    assert exc_info.value.status_code == 403


def test_leader_and_admin_can_edit_planning():
    assert require_planning_editor(make_user("leader")).role == "leader"
    assert require_planning_editor(make_user("admin")).role == "admin"
