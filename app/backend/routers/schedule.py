from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..audit import log as audit_log
from ..deps import get_current_user, get_db
from ..models import Activity, Person, ScheduleCell, User
from ..schemas import (
    CellOut,
    CellUpdate,
    PersonOut,
    ScheduleOut,
    SummaryRow,
)

router = APIRouter(prefix="/api/schedule", tags=["schedule"])

HOURS = list(range(6, 24))           # 06..23 = 18 timslots
HOURS_PER_PERSON_DAY = 8             # för persons_equiv = hours / 8


def _cell_to_dict(cell: ScheduleCell) -> dict:
    return {
        "person_id": cell.person_id,
        "hour": cell.hour,
        "activity_id": cell.activity_id,
        "version": cell.version,
        "updated_at": cell.updated_at.isoformat() if cell.updated_at else None,
        "updated_by": cell.updated_by,
    }


@router.get("", response_model=ScheduleOut)
def get_schedule(
    year: int = Query(..., ge=2000, le=2100),
    week: int = Query(..., ge=1, le=53),
    weekday: int = Query(..., ge=1, le=7),
    area_id: int | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ScheduleOut:
    persons_q = select(Person).where(Person.is_active.is_(True))
    if area_id is not None:
        persons_q = persons_q.where(Person.home_area_id == area_id)
    persons_q = persons_q.order_by(Person.sort_order, Person.name)
    persons = db.execute(persons_q).scalars().all()
    person_ids = [p.id for p in persons]

    cells: list[ScheduleCell] = []
    if person_ids:
        cells = (
            db.execute(
                select(ScheduleCell).where(
                    ScheduleCell.year == year,
                    ScheduleCell.week == week,
                    ScheduleCell.weekday == weekday,
                    ScheduleCell.person_id.in_(person_ids),
                )
            )
            .scalars()
            .all()
        )

    return ScheduleOut(
        year=year,
        week=week,
        weekday=weekday,
        area_id=area_id,
        persons=[PersonOut.model_validate(p) for p in persons],
        cells=[CellOut(**_cell_to_dict(c)) for c in cells],
    )


@router.put("/cell")
def update_cell(
    payload: CellUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.hour not in HOURS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Timme måste vara {HOURS[0]}-{HOURS[-1]}")

    if not db.get(Person, payload.person_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Person hittades inte")
    if payload.activity_id is not None and not db.get(Activity, payload.activity_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Aktivitet hittades inte")

    cell = (
        db.execute(
            select(ScheduleCell)
            .where(
                ScheduleCell.year == payload.year,
                ScheduleCell.week == payload.week,
                ScheduleCell.weekday == payload.weekday,
                ScheduleCell.hour == payload.hour,
                ScheduleCell.person_id == payload.person_id,
            )
            .with_for_update()
        )
        .scalar_one_or_none()
    )

    current_version = cell.version if cell else 0
    if current_version != payload.expected_version:
        current = (
            _cell_to_dict(cell)
            if cell
            else {
                "person_id": payload.person_id,
                "hour": payload.hour,
                "activity_id": None,
                "version": 0,
                "updated_at": None,
                "updated_by": None,
            }
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": "version_conflict", "current": current},
        )

    if cell is None:
        cell = ScheduleCell(
            year=payload.year,
            week=payload.week,
            weekday=payload.weekday,
            hour=payload.hour,
            person_id=payload.person_id,
            activity_id=payload.activity_id,
            version=1,
            updated_by=user.id,
        )
        db.add(cell)
        db.flush()
        audit_log(
            db,
            entity_type="schedule_cell",
            entity_id=cell.id,
            action="create",
            old_value=None,
            new_value=_cell_to_dict(cell),
            user_id=user.id,
        )
    else:
        old = _cell_to_dict(cell)
        cell.activity_id = payload.activity_id
        cell.version += 1
        cell.updated_by = user.id
        db.flush()
        audit_log(
            db,
            entity_type="schedule_cell",
            entity_id=cell.id,
            action="update",
            old_value=old,
            new_value=_cell_to_dict(cell),
            user_id=user.id,
        )

    db.commit()
    db.refresh(cell)
    return {"cell": _cell_to_dict(cell)}


@router.get("/summary", response_model=list[SummaryRow])
def get_summary(
    year: int = Query(..., ge=2000, le=2100),
    week: int = Query(..., ge=1, le=53),
    weekday: int = Query(..., ge=1, le=7),
    area_id: int | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[SummaryRow]:
    q = (
        select(
            Activity.id,
            Activity.code,
            Activity.label,
            Activity.color,
            func.count(ScheduleCell.id).label("hours"),
        )
        .join(ScheduleCell, ScheduleCell.activity_id == Activity.id)
        .where(
            ScheduleCell.year == year,
            ScheduleCell.week == week,
            ScheduleCell.weekday == weekday,
        )
        .group_by(Activity.id, Activity.code, Activity.label, Activity.color, Activity.sort_order)
        .order_by(Activity.sort_order)
    )
    if area_id is not None:
        q = q.join(Person, Person.id == ScheduleCell.person_id).where(Person.home_area_id == area_id)

    rows = db.execute(q).all()
    return [
        SummaryRow(
            activity_id=r.id,
            activity_code=r.code,
            activity_label=r.label,
            color=r.color,
            hours=r.hours,
            persons_equiv=round(r.hours / HOURS_PER_PERSON_DAY, 1),
        )
        for r in rows
    ]
