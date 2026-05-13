from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..audit import log as audit_log
from ..deps import get_current_user, get_db
from ..models import Activity, Person, ScheduleCell, User
from ..schemas import PersonOut
from ..template_service import get_template_hours

router = APIRouter(prefix="/api/overview", tags=["overview"])


class OverviewCell(BaseModel):
    person_id: int
    weekday: int
    activity_id: int | None
    mixed: bool
    hours_total: int
    template_hours: int


class OverviewOut(BaseModel):
    year: int
    week: int
    persons: list[PersonOut]
    matrix: list[OverviewCell]


class OverviewDayRequest(BaseModel):
    person_id: int
    year: int
    week: int
    weekday: int
    activity_id: int | None


@router.get("", response_model=OverviewOut)
def get_overview(
    year: int = Query(..., ge=2000, le=2100),
    week: int = Query(..., ge=1, le=53),
    area_id: int | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> OverviewOut:
    persons_q = select(Person).where(Person.is_active.is_(True))
    if area_id is not None:
        persons_q = persons_q.where(Person.home_area_id == area_id)
    persons_q = persons_q.order_by(Person.sort_order, Person.name)
    persons = db.execute(persons_q).scalars().all()
    person_ids = [p.id for p in persons]

    counts: dict[tuple[int, int, int | None], int] = defaultdict(int)
    if person_ids:
        rows = db.execute(
            select(
                ScheduleCell.person_id,
                ScheduleCell.weekday,
                ScheduleCell.activity_id,
                func.count(ScheduleCell.id),
            )
            .where(
                ScheduleCell.year == year,
                ScheduleCell.week == week,
                ScheduleCell.person_id.in_(person_ids),
            )
            .group_by(ScheduleCell.person_id, ScheduleCell.weekday, ScheduleCell.activity_id)
        ).all()
        for pid, wd, aid, cnt in rows:
            counts[(pid, wd, aid)] = cnt

    matrix: list[OverviewCell] = []
    for p in persons:
        for wd in range(1, 8):
            # Hämta alla aktiviteter för denna dag
            day_acts = [
                (aid, cnt) for (pid, weekday, aid), cnt in counts.items()
                if pid == p.id and weekday == wd and aid is not None
            ]
            hours_total = sum(c for _, c in day_acts)
            distinct = {aid for aid, _ in day_acts}
            if not day_acts:
                dominant = None
                mixed = False
            else:
                # välj den med flest timmar
                dominant = max(day_acts, key=lambda x: x[1])[0]
                mixed = len(distinct) > 1

            template = get_template_hours(db, p.id, wd)
            template_hours = 0 if template is None else len(template)

            matrix.append(OverviewCell(
                person_id=p.id, weekday=wd,
                activity_id=dominant, mixed=mixed,
                hours_total=hours_total, template_hours=template_hours,
            ))

    return OverviewOut(
        year=year, week=week,
        persons=[PersonOut.model_validate(p) for p in persons],
        matrix=matrix,
    )


@router.post("/day")
def set_day(
    payload: OverviewDayRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if not db.get(Person, payload.person_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Person hittades inte")
    if payload.activity_id is not None and not db.get(Activity, payload.activity_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Aktivitet hittades inte")

    template = get_template_hours(db, payload.person_id, payload.weekday)
    if template is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Personen är markerad som ledig denna dag. Ändra schemat först eller bemanna i bemanningsvyn.",
        )
    if not template:
        return {"written": 0, "deleted": 0}

    # Hämta befintliga cells INOM template-fönstret
    existing = db.execute(
        select(ScheduleCell).where(
            ScheduleCell.year == payload.year,
            ScheduleCell.week == payload.week,
            ScheduleCell.weekday == payload.weekday,
            ScheduleCell.person_id == payload.person_id,
            ScheduleCell.hour.in_(template),
        ).with_for_update()
    ).scalars().all()
    existing_by_hour = {c.hour: c for c in existing}

    written = 0
    deleted = 0

    for hour in sorted(template):
        cell = existing_by_hour.get(hour)
        if payload.activity_id is None:
            # Töm cellen / ta bort
            if cell is not None:
                audit_log(
                    db, entity_type="schedule_cell", entity_id=cell.id,
                    action="overview_day_clear",
                    old_value={"activity_id": cell.activity_id, "version": cell.version},
                    new_value=None, user_id=user.id,
                )
                db.delete(cell)
                deleted += 1
            continue

        if cell is None:
            cell = ScheduleCell(
                year=payload.year, week=payload.week, weekday=payload.weekday,
                hour=hour, person_id=payload.person_id,
                activity_id=payload.activity_id, version=1, updated_by=user.id,
            )
            db.add(cell)
            db.flush()
            audit_log(
                db, entity_type="schedule_cell", entity_id=cell.id,
                action="overview_day_assign", old_value=None,
                new_value={"activity_id": cell.activity_id, "version": 1}, user_id=user.id,
            )
            written += 1
        else:
            if cell.activity_id != payload.activity_id:
                old = {"activity_id": cell.activity_id, "version": cell.version}
                cell.activity_id = payload.activity_id
                cell.version += 1
                cell.updated_by = user.id
                db.flush()
                audit_log(
                    db, entity_type="schedule_cell", entity_id=cell.id,
                    action="overview_day_assign", old_value=old,
                    new_value={"activity_id": cell.activity_id, "version": cell.version},
                    user_id=user.id,
                )
                written += 1

    db.commit()
    return {"written": written, "deleted": deleted}
