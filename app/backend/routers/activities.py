from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_db, require_admin
from ..models import Activity
from ..schemas import ActivityCreate, ActivityOut, ActivityUpdate

router = APIRouter(prefix="/api/activities", tags=["activities"])


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
    _=Depends(require_admin),
) -> Activity:
    if db.query(Activity).filter_by(code=payload.code).first():
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Aktivitet med samma kod finns redan")
    activity = Activity(**payload.model_dump())
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


@router.put("/{activity_id}", response_model=ActivityOut)
def update_activity(
    activity_id: int,
    payload: ActivityUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> Activity:
    activity = db.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Aktivitet hittades inte")
    if payload.code is not None:
        existing = db.query(Activity).filter(Activity.code == payload.code, Activity.id != activity_id).first()
        if existing:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Aktivitet med samma kod finns redan")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(activity, key, value)
    db.commit()
    db.refresh(activity)
    return activity


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
) -> None:
    activity = db.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Aktivitet hittades inte")
    activity.is_active = False
    db.commit()
