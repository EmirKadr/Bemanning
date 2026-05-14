from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_db, require_admin
from ..models import User
from ..schemas import AppSettingsOut, AppSettingsUpdate
from ..settings_service import get_lock_foreign_schedule_cells, set_lock_foreign_schedule_cells

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _settings_out(db: Session) -> AppSettingsOut:
    return AppSettingsOut(
        lock_foreign_schedule_cells=get_lock_foreign_schedule_cells(db),
    )


@router.get("", response_model=AppSettingsOut)
def get_app_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> AppSettingsOut:
    return _settings_out(db)


@router.put("", response_model=AppSettingsOut)
def update_app_settings(
    payload: AppSettingsUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> AppSettingsOut:
    set_lock_foreign_schedule_cells(
        db,
        payload.lock_foreign_schedule_cells,
        user_id=admin.id,
    )
    db.commit()
    return _settings_out(db)
