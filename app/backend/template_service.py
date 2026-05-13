"""Hjälpfunktioner för person_schedule_templates."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import PersonScheduleTemplate

DEFAULT_START = 7
DEFAULT_END = 16  # exklusiv → timslots 7..15


def get_template_hours(db: Session, person_id: int, weekday: int) -> set[int] | None:
    """Returnera set av timmar (6..23) som personen ska bemannas på den dagen.

    None = ledig.
    Om ingen rad finns: default 07..15 (range(7, 16)).
    """
    row = db.execute(
        select(PersonScheduleTemplate).where(
            PersonScheduleTemplate.person_id == person_id,
            PersonScheduleTemplate.weekday == weekday,
        )
    ).scalar_one_or_none()

    if row is None:
        return set(range(DEFAULT_START, DEFAULT_END))
    if row.is_off:
        return None
    return set(range(row.start_hour, row.end_hour))


def get_all_default_days() -> list[dict]:
    """Standard-veckomall för en person som saknar sparade rader: vardagar 07-16, helg ledig."""
    days = []
    for wd in range(1, 8):
        if wd <= 5:
            days.append({"weekday": wd, "is_off": False, "start_hour": DEFAULT_START, "end_hour": DEFAULT_END})
        else:
            days.append({"weekday": wd, "is_off": True, "start_hour": None, "end_hour": None})
    return days
