from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..deps import require_super_user
from ..models import User
from ..productivity_service import ProductivitySourceError, build_productivity_report


router = APIRouter(prefix="/api/productivity", tags=["productivity"])


@router.get("")
def get_productivity(
    date_filter: date | None = Query(default=None, alias="date"),
    _: User = Depends(require_super_user),
) -> dict:
    try:
        return build_productivity_report(report_date=date_filter)
    except ProductivitySourceError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Kunde inte läsa produktivitetsunderlag: {exc}",
        ) from exc
