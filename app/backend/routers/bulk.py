from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..audit import log as audit_log
from ..deps import get_current_user, get_db
from ..models import Person, ScheduleCell, User
from ..schemas import ClearRequest, CopyRequest, FillFromLeftRequest

router = APIRouter(prefix="/api/schedule", tags=["schedule-bulk"])


def _person_ids_for_area(db: Session, area_id: int | None) -> list[int] | None:
    if area_id is None:
        return None
    rows = db.execute(select(Person.id).where(Person.home_area_id == area_id)).scalars().all()
    return list(rows)


@router.post("/copy")
def copy_schedule(
    payload: CopyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if (payload.from_weekday is None) != (payload.to_weekday is None):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Antingen båda eller ingen weekday")

    weekdays = (
        [payload.from_weekday] if payload.from_weekday is not None else [1, 2, 3, 4, 5, 6, 7]
    )
    to_weekdays = (
        [payload.to_weekday] if payload.to_weekday is not None else [1, 2, 3, 4, 5, 6, 7]
    )

    area_person_ids = _person_ids_for_area(db, payload.area_id)
    if area_person_ids is not None and not area_person_ids:
        return {"copied": 0}

    copied = 0
    for from_wd, to_wd in zip(weekdays, to_weekdays):
        src_q = select(ScheduleCell).where(
            ScheduleCell.year == payload.from_year,
            ScheduleCell.week == payload.from_week,
            ScheduleCell.weekday == from_wd,
        )
        if area_person_ids is not None:
            src_q = src_q.where(ScheduleCell.person_id.in_(area_person_ids))
        src_cells = db.execute(src_q).scalars().all()
        if not src_cells:
            continue

        # Hämta existerande mål-celler för att hantera overwrite
        person_ids_in_src = list({c.person_id for c in src_cells})
        existing_q = select(ScheduleCell).where(
            ScheduleCell.year == payload.to_year,
            ScheduleCell.week == payload.to_week,
            ScheduleCell.weekday == to_wd,
            ScheduleCell.person_id.in_(person_ids_in_src),
        )
        existing = {(c.person_id, c.hour): c for c in db.execute(existing_q).scalars().all()}

        for src in src_cells:
            key = (src.person_id, src.hour)
            target = existing.get(key)
            if target and not payload.overwrite:
                continue
            if target:
                old = {"activity_id": target.activity_id, "version": target.version}
                target.activity_id = src.activity_id
                target.version += 1
                target.updated_by = user.id
                db.flush()
                audit_log(
                    db,
                    entity_type="schedule_cell",
                    entity_id=target.id,
                    action="bulk_copy",
                    old_value=old,
                    new_value={"activity_id": target.activity_id, "version": target.version},
                    user_id=user.id,
                )
            else:
                new_cell = ScheduleCell(
                    year=payload.to_year,
                    week=payload.to_week,
                    weekday=to_wd,
                    hour=src.hour,
                    person_id=src.person_id,
                    activity_id=src.activity_id,
                    version=1,
                    updated_by=user.id,
                )
                db.add(new_cell)
                db.flush()
                audit_log(
                    db,
                    entity_type="schedule_cell",
                    entity_id=new_cell.id,
                    action="bulk_copy",
                    old_value=None,
                    new_value={"activity_id": new_cell.activity_id, "version": 1},
                    user_id=user.id,
                )
            copied += 1

    db.commit()
    return {"copied": copied}


@router.post("/clear")
def clear_schedule(
    payload: ClearRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    q = select(ScheduleCell).where(
        ScheduleCell.year == payload.year,
        ScheduleCell.week == payload.week,
        ScheduleCell.weekday == payload.weekday,
    )
    if payload.person_id is not None:
        q = q.where(ScheduleCell.person_id == payload.person_id)
    elif payload.area_id is not None:
        pids = _person_ids_for_area(db, payload.area_id)
        if not pids:
            return {"cleared": 0}
        q = q.where(ScheduleCell.person_id.in_(pids))

    cells = db.execute(q).scalars().all()
    for c in cells:
        audit_log(
            db,
            entity_type="schedule_cell",
            entity_id=c.id,
            action="clear",
            old_value={"activity_id": c.activity_id, "version": c.version},
            new_value=None,
            user_id=user.id,
        )
    cleared = len(cells)
    for c in cells:
        db.delete(c)
    db.commit()
    return {"cleared": cleared}


@router.post("/fill-from-left")
def fill_from_left(
    payload: FillFromLeftRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """För varje person: kopiera senaste icke-tomma aktivitet till efterföljande tomma celler samma dag."""
    pids = _person_ids_for_area(db, payload.area_id)
    q = select(ScheduleCell).where(
        ScheduleCell.year == payload.year,
        ScheduleCell.week == payload.week,
        ScheduleCell.weekday == payload.weekday,
    )
    if pids is not None:
        if not pids:
            return {"updated": 0}
        q = q.where(ScheduleCell.person_id.in_(pids))
    cells = db.execute(q).scalars().all()

    # Bygg map person → hour → cell
    per_person: dict[int, dict[int, ScheduleCell]] = {}
    for c in cells:
        per_person.setdefault(c.person_id, {})[c.hour] = c

    # Hämta alla aktuella personer i området (de utan celler ska också få chans att fyllas? nej, fill-from-left förutsätter befintliga celler)
    updated = 0
    HOURS = list(range(6, 24))

    person_ids = pids if pids is not None else list(per_person.keys())
    for pid in person_ids:
        last_activity_id: int | None = None
        for h in HOURS:
            existing = per_person.get(pid, {}).get(h)
            if existing and existing.activity_id is not None:
                last_activity_id = existing.activity_id
                continue
            if last_activity_id is None:
                continue
            if existing:
                # tom (activity_id is None) cell – fyll
                old = {"activity_id": existing.activity_id, "version": existing.version}
                existing.activity_id = last_activity_id
                existing.version += 1
                existing.updated_by = user.id
                db.flush()
                audit_log(
                    db,
                    entity_type="schedule_cell",
                    entity_id=existing.id,
                    action="fill_left",
                    old_value=old,
                    new_value={"activity_id": existing.activity_id, "version": existing.version},
                    user_id=user.id,
                )
                updated += 1
            else:
                new_cell = ScheduleCell(
                    year=payload.year,
                    week=payload.week,
                    weekday=payload.weekday,
                    hour=h,
                    person_id=pid,
                    activity_id=last_activity_id,
                    version=1,
                    updated_by=user.id,
                )
                db.add(new_cell)
                db.flush()
                audit_log(
                    db,
                    entity_type="schedule_cell",
                    entity_id=new_cell.id,
                    action="fill_left",
                    old_value=None,
                    new_value={"activity_id": last_activity_id, "version": 1},
                    user_id=user.id,
                )
                per_person.setdefault(pid, {})[h] = new_cell
                updated += 1

    db.commit()
    return {"updated": updated}
