import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api import admin, auth, connections, events, measurements, satellites, simulations, users
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
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",") if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

api = "/api/v1"
for router in (
    auth.router, users.router, satellites.router, simulations.router,
    connections.router, measurements.router, events.router, admin.router,
):
    app.include_router(router, prefix=api)


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(_: Request, __: SQLAlchemyError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": "A database operation failed"})


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "connectivity": "simulation_only"}