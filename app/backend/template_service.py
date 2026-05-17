"""Hjälpfunktioner för person_schedule_templates."""
from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Person, PersonScheduleTemplate

DEFAULT_START = 7
DEFAULT_END = 16          # exklusiv → timslots 7..15
LUNCH_OFFSET = 5          # lunchen sätts 5 timmar in i passet (start_hour + 5)


def _hours_with_lunch_removed(start: int, end: int) -> set[int]:
    """Returnera arbetstimmar inom [start, end) med lunchtimmen borttagen.

    Lunch = en timme, placerad 5 timmar in i passet. Om passet är kortare
    än så att lunchen inte ryms inom fönstret, ingen lunch dras av.
    """
    hours = set(range(start, end))
    lunch_hour = start + LUNCH_OFFSET
    hours.discard(lunch_hour)
    return hours


def _default_hours_for_weekday(weekday: int) -> set[int] | None:
    if weekday <= 5:
        return _hours_with_lunch_removed(DEFAULT_START, DEFAULT_END)
    return None


def get_template_hours(db: Session, person_id: int, weekday: int) -> set[int] | None:
    """Returnera set av timmar (6..23) som personen ska bemannas på den dagen.

    None = ledig.
    Om personen saknar egen mall: vardagar default 07..15 minus lunch, helg ledig.
    Om personen har en egen mall men saknar rad för dagen: ledig.
    """
    person = db.get(Person, person_id)
    if person is not None and not person.has_fixed_schedule:
        return None

    rows = db.execute(
        select(PersonScheduleTemplate).where(
            PersonScheduleTemplate.person_id == person_id
        )
    ).scalars().all()
    row = next((item for item in rows if int(item.weekday) == int(weekday)), None)

    if row is None:
        return None if rows else _default_hours_for_weekday(weekday)
    if row.is_off:
        return None
    return _hours_with_lunch_removed(row.start_hour, row.end_hour)


def get_template_hours_map(
    db: Session,
    person_ids: Iterable[int],
    weekdays: Iterable[int],
) -> dict[tuple[int, int], set[int] | None]:
    """Batchhämta schema för flera personer/veckodagar.

    Nyckeln i resultatet är ``(person_id, weekday)``.
    Om en rad saknas används samma defaultbeteende som i ``get_template_hours``.
    """
    unique_person_ids = sorted({int(person_id) for person_id in person_ids})
    unique_weekdays = sorted({int(weekday) for weekday in weekdays})
    if not unique_person_ids or not unique_weekdays:
        return {}

    rows = db.execute(
        select(PersonScheduleTemplate).where(
            PersonScheduleTemplate.person_id.in_(unique_person_ids),
        )
    ).scalars().all()
    fixed_schedule_by_person = {
        int(person_id): bool(has_fixed_schedule)
        for person_id, has_fixed_schedule in db.execute(
            select(Person.id, Person.has_fixed_schedule).where(Person.id.in_(unique_person_ids))
        ).all()
    }

    template_map: dict[tuple[int, int], set[int] | None] = {}
    for row in rows:
        if int(row.weekday) not in unique_weekdays:
            continue
        key = (int(row.person_id), int(row.weekday))
        if fixed_schedule_by_person.get(int(row.person_id), True) is False:
            template_map[key] = None
            continue
        if row.is_off:
            template_map[key] = None
        else:
            template_map[key] = _hours_with_lunch_removed(row.start_hour, row.end_hour)

    person_ids_with_custom_template = {int(row.person_id) for row in rows}
    for person_id in unique_person_ids:
        for weekday in unique_weekdays:
            if (person_id, weekday) in template_map:
                continue
            if fixed_schedule_by_person.get(person_id, True) is False:
                template_map[(person_id, weekday)] = None
                continue
            if person_id in person_ids_with_custom_template:
                template_map[(person_id, weekday)] = None
            else:
                template_map[(person_id, weekday)] = _default_hours_for_weekday(weekday)

    return template_map


def get_all_default_days() -> list[dict]:
    """Standard-veckomall för en person som saknar sparade rader: vardagar 07-16, helg ledig."""
    days = []
    for wd in range(1, 8):
        if wd <= 5:
            days.append({"weekday": wd, "is_off": False, "start_hour": DEFAULT_START, "end_hour": DEFAULT_END})
        else:
            days.append({"weekday": wd, "is_off": True, "start_hour": None, "end_hour": None})
    return days
