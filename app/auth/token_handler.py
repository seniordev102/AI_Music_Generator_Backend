from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException

from app.config import settings


class JWTTokenHandler:
    secret_key = settings.JWT_SECRET_KEY
    algorithm = settings.JWT_ALGORITHM
    refresh_token_expire_minutes = settings.JWT_REFRESH_TOKEN_EXPIRE_MINUTES
    access_token_expire_minutes = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES

    def create_access_token(self, data: dict, expires_delta: timedelta = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=self.access_token_expire_minutes
            )
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def create_refresh_token(self, data: dict, expires_delta: timedelta = None):
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=self.refresh_token_expire_minutes
            )
        to_encode = data.copy()
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    async def validate_refresh_token(self, refresh_token: str) -> str:
        try:
            payload = jwt.decode(
                refresh_token, self.secret_key, algorithms=[self.algorithm]
            )
            email = payload.get("sub")
            if email is None:
                raise HTTPException(status_code=400, detail="Invalid token")

            token_expiry_timestamp = payload.get("exp")
            current_timestamp = datetime.now(timezone.utc).timestamp()
            token_expired = current_timestamp > token_expiry_timestamp
            if token_expired:
                raise HTTPException(status_code=400, detail="Token has expired")

            return email

        except jwt.PyJWTError as e:
            raise HTTPException(status_code=400, detail="Invalid token")

    def decode_jwt(self, token: str) -> dict:
        try:
            decoded_token = jwt.decode(
                token, self.secret_key, algorithms=[self.algorithm]
            )
            return decoded_token
        except:
            return {}
