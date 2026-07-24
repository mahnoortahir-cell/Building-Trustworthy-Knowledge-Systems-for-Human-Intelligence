from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from app.auth.router import router as auth_router
from fastapi import FastAPI

from app.core.config import get_settings
from app.core.database import Base, engine
import app.models  # noqa: F401


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)
app.include_router(auth_router)

@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Welcome to NoorOS API",
        "version": settings.app_version,
    }


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "environment": settings.environment,
    }