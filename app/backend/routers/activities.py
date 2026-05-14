import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..audit import log as audit_log
from ..deps import get_current_user, get_db, require_admin
from ..models import Activity, Area, User
from ..schemas import ActivityCreate, ActivityOut, ActivityUpdate
from ..user_access import is_super_user

router = APIRouter(prefix="/api/activities", tags=["activities"])


def _code_part(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", normalized).strip("_")
    return normalized.upper()


def _activity_code_base(label: str, area: Area | None) -> str:
    label_part = _code_part(label) or "AKTIVITET"
    area_part = _code_part(area.code if area else None)
    if area_part and label_part != area_part and not label_part.startswith(f"{area_part}_"):
        return f"{area_part}_{label_part}"
    return label_part


def _unique_activity_code(db: Session, base: str) -> str:
    base = (base or "AKTIVITET")[:40].rstrip("_") or "AKTIVITET"
    candidate = base
    suffix = 2
    while db.query(Activity).filter_by(code=candidate).first():
        suffix_text = f"_{suffix}"
        candidate = f"{base[:40 - len(suffix_text)].rstrip('_')}{suffix_text}"
        suffix += 1
    return candidate


def _resolve_activity_code(db: Session, payload: ActivityCreate, admin: User) -> str:
    provided = (payload.code or "").strip()
    if provided:
        if not is_super_user(admin):
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Endast Super User kan ange aktivitetskod")
        code = _code_part(provided)
        if not code:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Aktivitetskod saknar giltiga tecken")
        if db.query(Activity).filter_by(code=code).first():
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Aktivitet med samma kod finns redan")
        return code

    area = db.get(Area, payload.area_id) if payload.area_id is not None else None
    return _unique_activity_code(db, _activity_code_base(payload.label, area))


def _activity_snapshot(activity: Activity) -> dict:
    return {
        "id": activity.id,
        "code": activity.code,
        "label": activity.label,
        "area_id": activity.area_id,
        "summary_activity_id": activity.summary_activity_id,
        "color": activity.color,
        "category": activity.category,
        "sort_order": activity.sort_order,
        "is_active": activity.is_active,
        "required_competency": activity.required_competency,
    }


def _validate_summary_activity(
    db: Session,
    *,
    activity_id: int | None,
    summary_activity_id: int | None,
) -> int | None:
    if summary_activity_id is None:
        return None
    if activity_id is not None and summary_activity_id == activity_id:
        return None

    target = db.get(Activity, summary_activity_id)
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Summeringsaktivitet hittades inte")

    if activity_id is None:
        return summary_activity_id

    visited = {activity_id}
    current = target
    while current.summary_activity_id is not None:
        if current.summary_activity_id in visited:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Summeringskoppling skapar en loop")
        visited.add(current.id)
        current = db.get(Activity, current.summary_activity_id)
        if current is None:
            break

    return summary_activity_id


@router.get("", response_model=list[ActivityOut])
def list_activities(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
) -> list[Activity]:
    q = db.query(Activity)
    if not include_inactive:
        q = q.filter(Activity.is_active.is_(True))
    return q.order_by(Activity.sort_order, Activity.label).all()


@router.post("", response_model=ActivityOut, status_code=status.HTTP_201_CREATED)
def create_activity(
    payload: ActivityCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Activity:
    data = payload.model_dump()
    data["code"] = _resolve_activity_code(db, payload, admin)
    data["summary_activity_id"] = _validate_summary_activity(
        db,
        activity_id=None,
        summary_activity_id=payload.summary_activity_id,
    )
    activity = Activity(**data)
    db.add(activity)
    db.flush()
    audit_log(
        db,
        entity_type="activity",
        entity_id=activity.id,
        action="create",
        old_value=None,
        new_value=_activity_snapshot(activity),
        user_id=admin.id,
    )
    db.commit()
    db.refresh(activity)
    return activity


@router.put("/{activity_id}", response_model=ActivityOut)
def update_activity(
    activity_id: int,
    payload: ActivityUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Activity:
    activity = db.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Aktivitet hittades inte")
    before = _activity_snapshot(activity)
    if payload.code is not None:
        if not is_super_user(admin):
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Endast Super User kan ändra aktivitetskod")
        payload.code = _code_part(payload.code)
        if not payload.code:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Aktivitetskod saknar giltiga tecken")
        existing = db.query(Activity).filter(Activity.code == payload.code, Activity.id != activity_id).first()
        if existing:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Aktivitet med samma kod finns redan")
    data = payload.model_dump(exclude_unset=True)
    if "summary_activity_id" in data:
        data["summary_activity_id"] = _validate_summary_activity(
            db,
            activity_id=activity_id,
            summary_activity_id=payload.summary_activity_id,
        )
    for key, value in data.items():
        setattr(activity, key, value)
    audit_log(
        db,
        entity_type="activity",
        entity_id=activity.id,
        action="update",
        old_value=before,
        new_value=_activity_snapshot(activity),
        user_id=admin.id,
    )
    db.commit()
    db.refresh(activity)
    return activity


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> None:
    activity = db.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Aktivitet hittades inte")
    before = _activity_snapshot(activity)
    activity.is_active = False
    audit_log(
        db,
        entity_type="activity",
        entity_id=activity.id,
        action="deactivate",
        old_value=before,
        new_value=_activity_snapshot(activity),
        user_id=admin.id,
    )
    db.commit()
