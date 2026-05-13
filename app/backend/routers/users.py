from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from .. import audit
from ..deps import get_db, require_admin
from ..models import User
from ..schemas import UserAdminOut, UserCreate, UserUpdate
from ..security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


def _find_username_conflict(db: Session, username: str, *, exclude_user_id: int | None = None) -> User | None:
    query = db.query(User).filter(func.lower(User.username) == username.lower())
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    return query.order_by(User.id.asc()).first()


def _active_admin_count(db: Session, *, exclude_user_id: int | None = None) -> int:
    query = db.query(func.count(User.id)).filter(User.role == "admin", User.is_active.is_(True))
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    return int(query.scalar() or 0)


def _user_snapshot(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "is_active": user.is_active,
    }


@router.get("", response_model=list[UserAdminOut])
def list_users(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> list[User]:
    query = db.query(User)
    if not include_inactive:
        query = query.filter(User.is_active.is_(True))
    return query.order_by(case((User.role == "admin", 0), else_=1), User.username.asc()).all()


@router.post("", response_model=UserAdminOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> User:
    if _find_username_conflict(db, payload.username):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Användarnamnet används redan")

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        role=payload.role,
        is_active=payload.is_active,
    )
    db.add(user)
    db.flush()

    audit.log(
        db,
        entity_type="user",
        entity_id=user.id,
        action="create",
        old_value=None,
        new_value=_user_snapshot(user),
        user_id=admin.id,
    )

    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserAdminOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Användare hittades inte")

    if payload.username is not None and _find_username_conflict(db, payload.username, exclude_user_id=user_id):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Användarnamnet används redan")

    new_role = payload.role if payload.role is not None else user.role
    new_is_active = payload.is_active if payload.is_active is not None else user.is_active
    removes_admin_access = user.role == "admin" and (new_role != "admin" or not new_is_active)
    if removes_admin_access and _active_admin_count(db, exclude_user_id=user.id) == 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Det måste finnas minst en aktiv administratör kvar",
        )

    before = _user_snapshot(user)
    updates = payload.model_dump(exclude_unset=True, exclude={"password"})
    for key, value in updates.items():
        setattr(user, key, value)
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)

    audit.log(
        db,
        entity_type="user",
        entity_id=user.id,
        action="update",
        old_value=before,
        new_value=_user_snapshot(user),
        user_id=admin.id,
    )

    db.commit()
    db.refresh(user)
    return user
