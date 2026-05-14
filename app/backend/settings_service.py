from __future__ import annotations

from sqlalchemy.orm import Session

from .models import AppSetting


LOCK_FOREIGN_SCHEDULE_CELLS_KEY = "lock_foreign_schedule_cells"


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "ja"}


def get_bool_setting(db: Session, key: str, *, default: bool = False) -> bool:
    row = db.get(AppSetting, key)
    return _parse_bool(row.value if row else None, default=default)


def set_bool_setting(db: Session, key: str, value: bool, *, user_id: int | None = None) -> AppSetting:
    row = db.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key, value=_bool_text(value), updated_by=user_id)
        db.add(row)
    else:
        row.value = _bool_text(value)
        row.updated_by = user_id
    db.flush()
    return row


def get_lock_foreign_schedule_cells(db: Session) -> bool:
    return get_bool_setting(db, LOCK_FOREIGN_SCHEDULE_CELLS_KEY, default=False)


def set_lock_foreign_schedule_cells(db: Session, value: bool, *, user_id: int | None = None) -> AppSetting:
    return set_bool_setting(db, LOCK_FOREIGN_SCHEDULE_CELLS_KEY, value, user_id=user_id)
