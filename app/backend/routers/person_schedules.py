from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import log as audit_log
from ..deps import get_current_user, get_db
from ..models import Person, PersonScheduleTemplate, User
from ..schemas import TemplateDay, TemplateOut, TemplateUpdate
from ..template_service import DEFAULT_END, DEFAULT_START, get_all_default_days

router = APIRouter(prefix="/api/persons", tags=["person-schedules"])


def _validate_day(day: TemplateDay) -> None:
    if day.is_off:
        if day.start_hour is not None or day.end_hour is not None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"Dag {day.weekday}: timmar måste vara null när is_off=true",
            )
    else:
        if day.start_hour is None or day.end_hour is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"Dag {day.weekday}: start_hour och end_hour krävs",
            )
        if not (6 <= day.start_hour < day.end_hour <= 24):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"Dag {day.weekday}: ogiltigt tidsintervall {day.start_hour}-{day.end_hour}",
            )


@router.get("/{person_id}/schedule", response_model=TemplateOut)
def get_schedule(
    person_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> TemplateOut:
    if not db.get(Person, person_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Person hittades inte")

    rows = db.execute(
        select(PersonScheduleTemplate).where(PersonScheduleTemplate.person_id == person_id)
    ).scalars().all()
    by_wd = {r.weekday: r for r in rows}

    days: list[TemplateDay] = []
    has_any = bool(rows)
    defaults = {d["weekday"]: d for d in get_all_default_days()}
    for wd in range(1, 8):
        r = by_wd.get(wd)
        if r is not None:
            days.append(TemplateDay(
                weekday=wd, is_off=r.is_off,
                start_hour=r.start_hour, end_hour=r.end_hour,
            ))
        elif has_any:
            # Personen har egna rader men inte för denna dag → tolka som ledig
            days.append(TemplateDay(weekday=wd, is_off=True))
        else:
            d = defaults[wd]
            days.append(TemplateDay(**d))

    return TemplateOut(person_id=person_id, days=days)


@router.put("/{person_id}/schedule", response_model=TemplateOut)
def put_schedule(
    person_id: int,
    payload: TemplateUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TemplateOut:
    if not db.get(Person, person_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Person hittades inte")

    seen = set()
    for day in payload.days:
        _validate_day(day)
        if day.weekday in seen:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Dubbel weekday {day.weekday}")
        seen.add(day.weekday)

    existing = db.execute(
        select(PersonScheduleTemplate).where(PersonScheduleTemplate.person_id == person_id)
    ).scalars().all()
    existing_by_wd = {r.weekday: r for r in existing}

    days_out: list[TemplateDay] = []
    for day in payload.days:
        row = existing_by_wd.get(day.weekday)
        if row is None:
            row = PersonScheduleTemplate(
                person_id=person_id,
                weekday=day.weekday,
                start_hour=day.start_hour,
                end_hour=day.end_hour,
                is_off=day.is_off,
                updated_by=user.id,
            )
            db.add(row)
            db.flush()
            audit_log(
                db, entity_type="person_schedule_template", entity_id=row.id,
                action="create", old_value=None,
                new_value={"weekday": day.weekday, "is_off": day.is_off,
                           "start_hour": day.start_hour, "end_hour": day.end_hour},
                user_id=user.id,
            )
        else:
            old = {"weekday": row.weekday, "is_off": row.is_off,
                   "start_hour": row.start_hour, "end_hour": row.end_hour}
            row.is_off = day.is_off
            row.start_hour = day.start_hour
            row.end_hour = day.end_hour
            row.updated_by = user.id
            db.flush()
            new = {"weekday": day.weekday, "is_off": day.is_off,
                   "start_hour": day.start_hour, "end_hour": day.end_hour}
            if old != new:
                audit_log(
                    db, entity_type="person_schedule_template", entity_id=row.id,
                    action="update", old_value=old, new_value=new, user_id=user.id,
                )
        days_out.append(TemplateDay(
            weekday=row.weekday, is_off=row.is_off,
            start_hour=row.start_hour, end_hour=row.end_hour,
        ))

    db.commit()
    return TemplateOut(person_id=person_id, days=sorted(days_out, key=lambda d: d.weekday))
