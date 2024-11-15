import jwt
from fastapi import Depends, FastAPI, HTTPException, Request
from jwt import ExpiredSignatureError, PyJWTError
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings


class AuthMiddleware(BaseHTTPMiddleware):

    unprotected_paths = [
        "/api/v1/",
        "/api/v1/token",
        "/api/v1/docs/",
        "/api/v1/openapi.json",
    ]

    async def dispatch(self, request: Request, call_next):
        # return await call_next(request)
        if request.url.path in self.unprotected_paths:
            return await call_next(request)

        token = request.headers.get("Authorization")
        if token and token.startswith("Bearer "):
            token = token.split("Bearer ")[1]
            try:
                jwt.decode(
                    token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
                )
            except ExpiredSignatureError:
                raise HTTPException(status_code=401, detail="Token has expired")
            except PyJWTError:
                raise HTTPException(status_code=401, detail="Invalid token")

            return await call_next(request)
        else:
            raise HTTPException(status_code=401, detail="Not authenticated")
