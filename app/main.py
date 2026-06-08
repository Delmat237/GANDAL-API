from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

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

OPENAPI_OPERATION_ROLES = {
    ("post", "/api/v1/auth/login"): "Public",
    ("post", "/api/v1/auth/register-admin"): "Public + SUPERADMIN_SECRET_KEY",
    ("get", "/api/v1/auth/me"): "Authentifié",
    ("post", "/api/v1/users/students"): "Admin/SuperAdmin",
    ("get", "/api/v1/users/students"): "Admin/SuperAdmin",
    ("get", "/api/v1/users/students/{student_id}"): "Admin/SuperAdmin",
    ("patch", "/api/v1/users/students/{student_id}"): "Admin/SuperAdmin",
    ("delete", "/api/v1/users/students/{student_id}"): "Admin/SuperAdmin",
    ("post", "/api/v1/users/teachers"): "Admin/SuperAdmin",
    ("get", "/api/v1/users/teachers"): "Authentifié",
    ("get", "/api/v1/users/teachers/{teacher_id}"): "Admin/SuperAdmin",
    ("patch", "/api/v1/users/teachers/{teacher_id}"): "Admin/SuperAdmin",
    ("delete", "/api/v1/users/teachers/{teacher_id}"): "Admin/SuperAdmin",
    ("post", "/api/v1/vms"): "Admin/SuperAdmin",
    ("get", "/api/v1/vms"): "Authentifié",
    ("get", "/api/v1/vms/{vm_id}"): "Propriétaire ou Admin/SuperAdmin",
    ("patch", "/api/v1/vms/{vm_id}"): "Propriétaire ou Admin/SuperAdmin",
    ("delete", "/api/v1/vms/{vm_id}"): "Propriétaire ou Admin/SuperAdmin",
    ("post", "/api/v1/vms/{vm_id}/start"): "Propriétaire ou Admin/SuperAdmin",
    ("post", "/api/v1/vms/{vm_id}/stop"): "Propriétaire ou Admin/SuperAdmin",
    ("post", "/api/v1/vms/{vm_id}/pause"): "Propriétaire ou Admin/SuperAdmin",
    ("post", "/api/v1/requetes/create-vm"): "Student",
    ("post", "/api/v1/requetes/delete-vm"): "Student propriétaire de la VM",
    ("post", "/api/v1/requetes/account"): "Student",
    ("get", "/api/v1/requetes"): "Authentifié",
    (
        "get",
        "/api/v1/requetes/{requete_id}",
    ): "Étudiant auteur, enseignant assigné ou Admin/SuperAdmin",
    (
        "post",
        "/api/v1/requetes/{requete_id}/approve",
    ): "Enseignant assigné ou Admin/SuperAdmin",
    (
        "post",
        "/api/v1/requetes/{requete_id}/reject",
    ): "Enseignant assigné ou Admin/SuperAdmin",
    ("get", "/api/v1/publications/public"): "Public",
    ("post", "/api/v1/publications"): "Teacher ou Admin/SuperAdmin",
    ("get", "/api/v1/publications"): "Authentifié",
    ("get", "/api/v1/publications/{publication_id}"): "Authentifié",
    (
        "patch",
        "/api/v1/publications/{publication_id}",
    ): "Enseignant propriétaire ou Admin/SuperAdmin",
    (
        "delete",
        "/api/v1/publications/{publication_id}",
    ): "Enseignant propriétaire ou Admin/SuperAdmin",
    ("get", "/api/v1/dns"): "Admin/SuperAdmin",
    ("get", "/api/v1/dns/vms/{vm_id}"): "Propriétaire de la VM ou Admin/SuperAdmin",
    ("post", "/api/v1/dns"): "Propriétaire de la VM ou Admin/SuperAdmin",
    ("get", "/api/v1/dns/{dns_id}"): "Propriétaire de la VM ou Admin/SuperAdmin",
    ("patch", "/api/v1/dns/{dns_id}"): "Propriétaire de la VM ou Admin/SuperAdmin",
    ("delete", "/api/v1/dns/{dns_id}"): "Propriétaire de la VM ou Admin/SuperAdmin",
    ("get", "/health"): "Public",
    ("get", "/ready"): "Public",
}


def install_openapi_permissions(app: FastAPI) -> None:
    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
        )

        for (method, path), role in OPENAPI_OPERATION_ROLES.items():
            operation = openapi_schema.get("paths", {}).get(path, {}).get(method)
            if not operation:
                continue

            summary = operation.get("summary")
            operation["summary"] = f"{role} - {summary}" if summary else role

            description = operation.get("description")
            role_description = f"**Rôle autorisé :** {role}"
            operation["description"] = (
                f"{role_description}\n\n{description}" if description else role_description
            )
            operation["x-authorized-role"] = role

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi


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

    install_openapi_permissions(app)

    return app


app = create_app()
