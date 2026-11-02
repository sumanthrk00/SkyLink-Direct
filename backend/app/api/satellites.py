from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import count_for, paginated
from app.api.deps import get_current_user
from app.database import get_db
from app.models.models import Satellite, User
from app.schemas.schema import PageResponse, SatelliteResponse

router = APIRouter(prefix="/satellites", tags=["satellites"])


@router.get("", response_model=PageResponse)
def list_satellites(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    statement = select(Satellite).order_by(Satellite.name)
    result = paginated(db, statement, count_for(Satellite), limit, offset)
    result["items"] = [SatelliteResponse.model_validate(item).model_dump(mode="json") for item in result["items"]]
    return result


@router.get("/{satellite_id}", response_model=SatelliteResponse)
def get_satellite(satellite_id: UUID, _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Satellite:
    satellite = db.get(Satellite, satellite_id)
    if satellite is None:
        raise HTTPException(status_code=404, detail="Satellite not found")
    return satellite
