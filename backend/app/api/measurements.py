from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import count_for, paginated
from app.api.deps import get_current_user
from app.database import get_db
from app.models.models import ConnectionSession, SignalMeasurement, User
from app.schemas.schema import PageResponse

router = APIRouter(prefix="/measurements", tags=["measurements"])


@router.get("", response_model=PageResponse)
def list_measurements(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    owned_sessions = select(ConnectionSession.id).where(ConnectionSession.user_id == user.id)
    statement = select(SignalMeasurement).where(SignalMeasurement.session_id.in_(owned_sessions)).order_by(
        SignalMeasurement.measured_at.desc()
    )
    count = count_for(SignalMeasurement).where(SignalMeasurement.session_id.in_(owned_sessions))
    result = paginated(db, statement, count, limit, offset)
    result["items"] = [{
        "id": str(item.id), "session_id": str(item.session_id), "signal_strength": item.signal_strength,
        "latency_ms": item.latency_ms, "packet_loss": item.packet_loss, "measured_at": item.measured_at.isoformat(),
    } for item in result["items"]]
    return result
