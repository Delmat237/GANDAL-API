from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import check_db_connection
from app.core.exceptions import register_exception_handlers
from app.core.logging_config import setup_logging
from app.features.auth.router import router as auth_router
from app.features.dns.router import router as dns_router
from app.features.publications.router import router as publications_router
from app.features.requetes.router import router as requetes_router
from app.features.users.router import router as users_router
from app.features.vms.router import router as vms_router

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="dc-backend",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    register_exception_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    prefix = "/api/v1"
    app.include_router(auth_router, prefix=prefix)
    app.include_router(users_router, prefix=prefix)
    app.include_router(vms_router, prefix=prefix)
    app.include_router(requetes_router, prefix=prefix)
    app.include_router(publications_router, prefix=prefix)
    app.include_router(dns_router, prefix=prefix)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/ready")
    def ready() -> dict:
        db_ok = check_db_connection()
        return {"status": "ready" if db_ok else "degraded", "database": db_ok}

    return app


app = create_app()
