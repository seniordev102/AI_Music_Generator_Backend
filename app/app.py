# from api.router import api_router
from datetime import datetime

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, UJSONResponse
from sqlmodel import SQLModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.common.http_response_model import CommonResponse
from app.common.middleware import log_request_middleware
from app.config import settings
from app.database import async_engine
from app.ws.ws_manager import sio_app


async def init_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


def get_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0",
        docs_url=f"{settings.API_PREFIX}/docs/",
        redoc_url=f"{settings.API_PREFIX}/redoc/",
        openapi_url=f"{settings.API_PREFIX}/openapi.json",
        default_response_class=UJSONResponse,
    )

    @app.on_event("startup")
    async def on_startup():
        await init_db()

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.mount("/ws", app=sio_app)

    @app.get("/", name="IAH backend service")
    async def root():
        return {
            "message": "IAH backend service",
            "description": "iah.fit is a holistic wellness platform that combines ancient wisdom with modern science",
            "version": "1.1.0",
            "documentation": f"{settings.API_PREFIX}/docs/",
            "redoc": f"{settings.API_PREFIX}/redoc/",
            "openapi": f"{settings.API_PREFIX}/openapi.json",
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "environment": settings.APP_ENV,
        }

    # index route for health check
    @app.get("/api/v1/db-init", name="initializing Database")
    async def root():
        await init_db()
        return {"message": "Database initialized"}

    @app.get("/api/v1/health-check", name="Health Check")
    async def root():
        return {"message": "I am healthy iah backend service v3"}

    app.include_router(router=api_router, prefix="/api/v1")

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        error_message = exc.detail if exc.detail else "An error occurred."
        status_code = (
            exc.status_code
            if exc.status_code
            else status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        response = CommonResponse(success=False, message=error_message, payload=[])
        return JSONResponse(status_code=status_code, content=response.dict())

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc):
        response = CommonResponse(
            success=False, message="Unprocessable Entity", payload=str(exc)
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=response.dict()
        )

    app.middleware("http")(log_request_middleware)

    return app
