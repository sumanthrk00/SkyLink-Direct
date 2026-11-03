import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api import admin, auth, connections, events, gateways, ground_stations, measurements, network, satellites, simulations, users
from app.database import Base, SessionLocal, engine
from app.models import models  # noqa: F401
from app.services.bootstrap import initialize_reference_data


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        initialize_reference_data(db)
    yield


app = FastAPI(
    title="SkyLink Direct API",
    description="A prototype API for illustrative satellite visibility and connectivity simulations. Not real satellite service.",
    version="1.0.0",
    lifespan=lifespan,
)

allowed_origins = [
    origin.strip() for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:3000,http://127.0.0.1:3000"
    ).split(",") if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = "/api/v1"
for router in (
    auth.router, users.router, satellites.router, simulations.router,
    connections.router, measurements.router, events.router, admin.router,
    ground_stations.router, gateways.router, network.router,
):
    app.include_router(router, prefix=api)


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(_: Request, __: SQLAlchemyError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": "A database operation failed"})


@app.get("/health", tags=["health"])
@app.get("/api/v1/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "connectivity": "simulation_only"}
