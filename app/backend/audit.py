"""Helper för att skriva audit_log-rader i samma transaktion som mutationen."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .models import AuditLog


def log(
    db: Session,
    entity_type: str,
    entity_id: int,
    action: str,
    old_value: dict[str, Any] | None,
    new_value: dict[str, Any] | None,
    user_id: int | None,
) -> None:
    db.add(
        AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            old_value=old_value,
            new_value=new_value,
            user_id=user_id,
        )
    )
