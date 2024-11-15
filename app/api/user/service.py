from typing import List

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.auth_handler import AuthHandler
from app.auth.token_handler import JWTTokenHandler
from app.config import settings
from app.database import db_session
from app.models import User
from app.schemas import UpdateAPIUsage, UpdateUser


class UserService:
    def __init__(
        self,
        # auth_handler: AuthHandler = AuthHandler(),
        session: AsyncSession = Depends(db_session),
        auth_handler: AuthHandler = AuthHandler(),
    ) -> None:
        self.session = session
        self.auth_handler = auth_handler

    # get a user by email

    async def get_user_by_email(self, email: str) -> User:
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required"
            )
        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user = user_record.scalar_one_or_none()
        return user

    # update user by user email
    async def update_user(self, email: str, update_data: UpdateUser) -> User:
        user = await self.get_user_by_email(email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        update_data_dict = update_data.dict(exclude_unset=True)
        if "email" in update_data_dict:
            existing_user = await self.get_user_by_email(update_data_dict["email"])
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email is already in use",
                )

        for field, value in update_data_dict.items():
            setattr(user, field, value)

        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)

        # updated user values
        return user

    # delete user by user email
    async def delete_user(self, email: str) -> bool:
        user = await self.get_user_by_email(email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        await self.session.delete(user)
        await self.session.commit()
        return True

    # change user password
    async def change_password(
        self, email: str, current_password: str, new_password: str
    ) -> bool:
        user = await self.get_user_by_email(email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # check if current password is correct
        is_valid_password = self.auth_handler.verify_password(
            current_password.encode("utf-8"), user.hashed_password
        )
        if not is_valid_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )

        # hash new password
        hashed_password = self.auth_handler.hash_password(new_password)
        user.hashed_password = hashed_password.decode("utf-8")

        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return True

    async def update_user_api_consumption(
        self, email: str, update_payload: UpdateAPIUsage
    ) -> User:

        user = await self.get_user_by_email(email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        update_key = update_payload.update_key.value

        # before updating check the configuration limit
        if user.numbers_of_ask_iah_queries >= user.monthly_limit_ask_iah_queries:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Request limit reached",
            )

        if (
            user.numbers_of_ask_iah_playlist_generation
            >= user.monthly_limit_ask_iah_playlist_generation
        ):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Request limit reached",
            )

        current_value = getattr(user, update_key, 0)
        setattr(user, update_key, current_value + 1)

        # raise HTTPException(
        #     status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        #     detail="Request limit reached",
        # )

        # update user api consumption
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)

        return user

    async def search_users_by_name_or_email(self, query: str) -> List[User]:
        user_records = await self.session.execute(
            select(User)
            .where(or_(User.name.ilike(f"%{query}%"), User.email.ilike(f"%{query}%")))
            .limit(10)
        )
        return user_records.scalars().all()

    async def get_user_from_user_id(self, user_id: str) -> User:
        user_record = await self.session.execute(select(User).where(User.id == user_id))
        return user_record.scalar_one_or_none()
