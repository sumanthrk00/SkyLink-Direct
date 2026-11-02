from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import count_for, paginated
from app.api.deps import get_current_user
from app.database import get_db
from app.models.models import NetworkEvent, User
from app.schemas.schema import PageResponse

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=PageResponse)
def list_events(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    statement = select(NetworkEvent).where(NetworkEvent.user_id == user.id).order_by(NetworkEvent.created_at.desc())
    result = paginated(db, statement, count_for(NetworkEvent).where(NetworkEvent.user_id == user.id), limit, offset)
    result["items"] = [{
        "id": str(item.id), "event_type": item.event_type, "description": item.description,
        "created_at": item.created_at.isoformat(),
    } for item in result["items"]]
    return result
