from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..deps import get_db, require_super_user
from ..models import AuditLog, User
from ..schemas import AuditEntryOut, AuditSummaryBucket, AuditSummaryOut

router = APIRouter(prefix="/api/audit", tags=["audit"])


def _apply_filters(query, *, user_id: int | None, entity_type: str | None, action: str | None,
                   entity_id: int | None, from_at: datetime | None, to_at: datetime | None):
    if user_id is not None:
        query = query.where(AuditLog.user_id == user_id)
    if entity_id is not None:
        query = query.where(AuditLog.entity_id == entity_id)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type.strip())
    if action:
        query = query.where(AuditLog.action.ilike(f"%{action.strip()}%"))
    if from_at is not None:
        query = query.where(AuditLog.created_at >= from_at)
    if to_at is not None:
        query = query.where(AuditLog.created_at <= to_at)
    return query


def _bucket(key: str | None, label: str | None, count: int) -> AuditSummaryBucket:
    normalized_key = key or "system"
    normalized_label = label or ("System" if normalized_key == "system" else normalized_key)
    return AuditSummaryBucket(key=normalized_key, label=normalized_label, count=int(count))


@router.get("", response_model=list[AuditEntryOut])
def list_audit_entries(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user_id: int | None = Query(None),
    entity_type: str | None = Query(None),
    action: str | None = Query(None),
    entity_id: int | None = Query(None),
    from_at: datetime | None = Query(None),
    to_at: datetime | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_super_user),
) -> list[AuditEntryOut]:
    query = (
        select(AuditLog, User.username, User.display_name)
        .outerjoin(User, User.id == AuditLog.user_id)
    )
    query = _apply_filters(
        query,
        user_id=user_id,
        entity_type=entity_type,
        action=action,
        entity_id=entity_id,
        from_at=from_at,
        to_at=to_at,
    )
    query = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset(offset).limit(limit)

    rows = db.execute(query).all()
    return [
        AuditEntryOut(
            id=audit.id,
            entity_type=audit.entity_type,
            entity_id=audit.entity_id,
            action=audit.action,
            old_value=audit.old_value,
            new_value=audit.new_value,
            user_id=audit.user_id,
            username=username,
            display_name=display_name,
            created_at=audit.created_at,
        )
        for audit, username, display_name in rows
    ]


@router.get("/summary", response_model=AuditSummaryOut)
def audit_summary(
    user_id: int | None = Query(None),
    entity_type: str | None = Query(None),
    action: str | None = Query(None),
    entity_id: int | None = Query(None),
    from_at: datetime | None = Query(None),
    to_at: datetime | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_super_user),
) -> AuditSummaryOut:
    base = select(AuditLog.id).select_from(AuditLog)
    base = _apply_filters(
        base,
        user_id=user_id,
        entity_type=entity_type,
        action=action,
        entity_id=entity_id,
        from_at=from_at,
        to_at=to_at,
    )

    total_events = int(db.execute(select(func.count()).select_from(base.subquery())).scalar() or 0)

    last_24_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_query = _apply_filters(
        select(func.count()).select_from(AuditLog),
        user_id=user_id,
        entity_type=entity_type,
        action=action,
        entity_id=entity_id,
        from_at=from_at,
        to_at=to_at,
    ).where(AuditLog.created_at >= last_24_cutoff)
    events_last_24h = int(db.execute(recent_query).scalar() or 0)

    distinct_users_query = _apply_filters(
        select(func.count(func.distinct(AuditLog.user_id))).select_from(AuditLog),
        user_id=user_id,
        entity_type=entity_type,
        action=action,
        entity_id=entity_id,
        from_at=from_at,
        to_at=to_at,
    ).where(AuditLog.user_id.is_not(None))
    unique_users = int(db.execute(distinct_users_query).scalar() or 0)

    users_query = (
        select(AuditLog.user_id, User.username, User.display_name, func.count().label("count"))
        .select_from(AuditLog)
        .outerjoin(User, User.id == AuditLog.user_id)
    )
    users_query = _apply_filters(
        users_query,
        user_id=user_id,
        entity_type=entity_type,
        action=action,
        entity_id=entity_id,
        from_at=from_at,
        to_at=to_at,
    )
    users_query = (
        users_query
        .group_by(AuditLog.user_id, User.username, User.display_name)
        .order_by(func.count().desc(), User.username.asc())
        .limit(8)
    )
    top_users = [
        _bucket(
            str(row.user_id) if row.user_id is not None else "system",
            row.display_name or row.username or "System",
            row.count,
        )
        for row in db.execute(users_query)
    ]

    actions_query = _apply_filters(
        select(AuditLog.action, func.count().label("count")).select_from(AuditLog),
        user_id=user_id,
        entity_type=entity_type,
        action=action,
        entity_id=entity_id,
        from_at=from_at,
        to_at=to_at,
    )
    actions_query = actions_query.group_by(AuditLog.action).order_by(func.count().desc(), AuditLog.action.asc()).limit(8)
    top_actions = [_bucket(row.action, row.action, row.count) for row in db.execute(actions_query)]

    entities_query = _apply_filters(
        select(AuditLog.entity_type, func.count().label("count")).select_from(AuditLog),
        user_id=user_id,
        entity_type=entity_type,
        action=action,
        entity_id=entity_id,
        from_at=from_at,
        to_at=to_at,
    )
    entities_query = (
        entities_query
        .group_by(AuditLog.entity_type)
        .order_by(func.count().desc(), AuditLog.entity_type.asc())
        .limit(8)
    )
    top_entities = [_bucket(row.entity_type, row.entity_type, row.count) for row in db.execute(entities_query)]

    return AuditSummaryOut(
        total_events=total_events,
        events_last_24h=events_last_24h,
        unique_users=unique_users,
        top_users=top_users,
        top_actions=top_actions,
        top_entities=top_entities,
    )
