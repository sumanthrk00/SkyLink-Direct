from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database import get_db
from app.models.models import ConnectionSession, NetworkEvent, Satellite, SimulationRun, User

router = APIRouter(prefix="/admin", tags=["administration"])


@router.get("/dashboard")
def dashboard(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, int]:
    return {
        "total_users": int(db.scalar(select(func.count()).select_from(User)) or 0),
        "total_satellites": int(db.scalar(select(func.count()).select_from(Satellite)) or 0),
        "total_simulations": int(db.scalar(select(func.count()).select_from(SimulationRun)) or 0),
        "active_sessions": int(db.scalar(select(func.count()).select_from(ConnectionSession).where(
            ConnectionSession.status == "connected"
        )) or 0),
        "network_events": int(db.scalar(select(func.count()).select_from(NetworkEvent)) or 0),
    }
