from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_db
from ..models import User
from ..schemas import LoginRequest, PasswordSetRequest, UserOut
from ..security import hash_password, verify_password
from ..user_access import user_needs_password_setup, user_out

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> UserOut:
    user = db.query(User).filter_by(username=payload.username).one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Felaktigt användarnamn eller lösenord")
    if user.password_hash is None:
        if payload.password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Lämna lösenordet tomt vid första inloggningen",
            )
    elif not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Felaktigt användarnamn eller lösenord")
    request.session["user_id"] = user.id
    return user_out(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request) -> None:
    request.session.clear()


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return user_out(user)


@router.post("/set-password", response_model=UserOut)
def set_password(
    payload: PasswordSetRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    if not user_needs_password_setup(user):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Lösenord är redan skapat")
    user.password_hash = hash_password(payload.password)
    user.must_change_password = False
    db.commit()
    db.refresh(user)
    return user_out(user)
