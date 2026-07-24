from fastapi import FastAPI

from app.auth.router import router as auth_router
from app.core.config import settings
from app.organizations.router import router as organizations_router


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

app.include_router(auth_router)
app.include_router(organizations_router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Welcome to NoorOS API",
    }


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "environment": settings.environment,
    }