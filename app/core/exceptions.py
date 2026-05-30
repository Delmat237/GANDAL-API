from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Ressource introuvable"):
        super().__init__(message, status_code=404)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Accès refusé"):
        super().__init__(message, status_code=403)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Non authentifié"):
        super().__init__(message, status_code=401)


class ConflictError(AppError):
    def __init__(self, message: str = "Conflit"):
        super().__init__(message, status_code=409)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})
