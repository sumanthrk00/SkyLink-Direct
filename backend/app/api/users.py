from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.core.security import hash_password, verify_password
from app.models.models import User
from app.schemas.schema import PasswordUpdateRequest, UserResponse, UserUpdateRequest

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
def get_profile(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(id=user.id, name=user.name, email=user.email, role=user.role.name, created_at=user.created_at)


@router.put("/me", response_model=UserResponse)
def update_profile(
    payload: UserUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    user.name = payload.name.strip()
    db.commit()
    db.refresh(user)
    return UserResponse(id=user.id, name=user.name, email=user.email, role=user.role.name, created_at=user.created_at)


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def update_password(
    payload: PasswordUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
