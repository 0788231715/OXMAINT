from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import settings
from backend.app.modules.asset_management.api.asset_categories import (
    router as asset_categories_router,
)
from backend.app.modules.asset_management.api.assets import (
    router as assets_router,
)
from backend.app.modules.service_requests.api.service_requests import (
    router as service_requests_router,
)
from backend.app.modules.user_management.api.auth import (
    router as auth_router,
)
from backend.app.modules.user_management.api.users import (
    router as users_router,
)
from backend.app.api.v1.organizations import router as organizations_router


app = FastAPI(
    title=settings.APP_NAME,
    description="Operations, Maintenance and Asset Management Platform",
    version=settings.APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# API routes
app.include_router(
    auth_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    users_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    assets_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    asset_categories_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    service_requests_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    organizations_router,
    prefix=settings.API_V1_PREFIX,
)


@app.get("/")
def root():
    return {
        "application": settings.APP_NAME,
        "message": "OxMaint backend is running",
        "version": settings.APP_VERSION,
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "application": settings.APP_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
