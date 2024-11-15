from datetime import datetime, timezone
from typing import Union

import bcrypt
from fastapi import HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from itsdangerous import URLSafeTimedSerializer

from app.auth.token_handler import JWTTokenHandler
from app.common.http_response_model import CommonResponse
from app.config import settings


class AuthHandler(HTTPBearer):
    def __init__(
        self,
        auto_error: bool = True,
        token_handler: JWTTokenHandler = JWTTokenHandler(),
    ):
        super(AuthHandler, self).__init__(auto_error=auto_error)
        self.token_handler = token_handler

    async def __call__(self, request: Request, response: Response):
        header_authorization: str = request.headers.get("Authorization")
        query_authorization: str = request.query_params.get("token")
        authorization = header_authorization or query_authorization

        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization token is missing. Please provide a valid token.",
            )
        credentials: HTTPAuthorizationCredentials = await super(
            AuthHandler, self
        ).__call__(request)
        if credentials:
            if not credentials.scheme == "Bearer":
                payload = CommonResponse(
                    success=False,
                    message="Invalid authentication scheme.",
                    payload=None,
                )
                response.status_code = 403
                return payload
            email = self.verify_jwt(credentials.credentials, response)
            if not email:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication credentials.",
                )
            return email
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization code.",
            )

    def verify_jwt(self, jwtoken: str, response: Response):
        try:
            payload = self.token_handler.decode_jwt(jwtoken)
            token_expiry_timestamp = payload.get("exp")
            current_timestamp = datetime.now(timezone.utc).timestamp()
            token_expired = current_timestamp > token_expiry_timestamp
            if token_expired:
                payload = CommonResponse(
                    success=False,
                    message="Invalid token or expired token.",
                    payload=None,
                )
                response.status_code = 403
                return payload
            email = payload.get("sub")
            if email:
                return email
            return None
        except:
            return None

    def hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(plain_password, hashed_password.encode("utf-8"))

    def generate_random_password(self) -> str:
        return bcrypt.gensalt()

    def generate_token_for_rest_password_email(self, email):
        serializer = URLSafeTimedSerializer(settings.JWT_SECRET_KEY)
        return serializer.dumps(email, salt=settings.EMAIL_TOKEN_SALT)

    def verify_reset_password_token(self, token) -> Union[str, bool]:
        serializer = URLSafeTimedSerializer(settings.JWT_SECRET_KEY)
        try:
            email = serializer.loads(
                token,
                salt=settings.EMAIL_TOKEN_SALT,
                max_age=settings.EMAIL_EXPIRE_SECONDS,
            )
        except Exception as SignatureExpired:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rest link has been expired",
            )
        return email
