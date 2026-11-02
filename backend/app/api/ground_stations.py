from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import count_for, paginated
from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.models import GroundStation, NetworkEvent, User
from app.schemas.schema import GroundStationCreateRequest, GroundStationResponse, PageResponse

router = APIRouter(prefix="/ground-stations", tags=["ground-stations"])


@router.get("", response_model=PageResponse)
def list_ground_stations(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    statement = select(GroundStation).order_by(GroundStation.name.asc())
    result = paginated(db, statement, count_for(GroundStation), limit, offset)
    result["items"] = [GroundStationResponse.model_validate(item).model_dump(mode="json") for item in result["items"]]
    return result


@router.get("/{station_id}", response_model=GroundStationResponse)
def get_ground_station(
    station_id: UUID,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GroundStationResponse:
    station = db.get(GroundStation, station_id)
    if station is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ground station not found")
    return GroundStationResponse.model_validate(station)


@router.post("", response_model=GroundStationResponse, status_code=status.HTTP_201_CREATED)
def create_ground_station(
    payload: GroundStationCreateRequest,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> GroundStationResponse:
    if db.scalar(select(GroundStation).where(GroundStation.name == payload.name.strip())) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A ground station with this name already exists")
    station = GroundStation(
        name=payload.name.strip(),
        latitude_deg=payload.latitude_deg,
        longitude_deg=payload.longitude_deg,
        status=payload.status,
    )
    db.add(station)
    db.add(NetworkEvent(user_id=user.id, event_type="ground_station.created", description=f"Ground station {station.name} created"))
    db.commit()
    db.refresh(station)
    return GroundStationResponse.model_validate(station)

