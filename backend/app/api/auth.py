from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import bearer_scheme, get_current_user
from app.core.rate_limit import enforce_auth_rate_limit
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.database import get_db
from app.models.models import NetworkEvent, RevokedToken, Role, User
from app.schemas.schema import LoginRequest, RegisterRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["authentication"])


def response_for(user: User) -> UserResponse:
    return UserResponse(
        id=user.id, name=user.name, email=user.email, role=user.role.name, created_at=user.created_at
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(enforce_auth_rate_limit)])
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> UserResponse:
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")
    role = db.scalar(select(Role).where(Role.name == "user"))
    if role is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="User roles are not initialized")
    user = User(name=payload.name.strip(), email=email, password_hash=hash_password(payload.password), role=role)
    db.add(user)
    db.add(NetworkEvent(event_type="user.registered", description="A user registered"))
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists") from None
    return response_for(user)


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(enforce_auth_rate_limit)])
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    token, _, _ = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    payload = decode_access_token(credentials.credentials)
    expires_at = payload["exp"]
    if isinstance(expires_at, (int, float)):
        expires_at = datetime.fromtimestamp(expires_at, tz=timezone.utc)
    db.add(RevokedToken(jti=payload["jti"], expires_at=expires_at))
    db.commit()
