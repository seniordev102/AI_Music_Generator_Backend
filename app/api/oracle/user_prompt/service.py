from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import db_session
from app.models import IAHUserPrompt, SRAUserPrompt, User


class UserCustomPromptService:
    def __init__(self, session: AsyncSession = Depends(db_session)) -> None:
        self.session = session

    async def create_or_update_iah_user_custom_prompt(
        self, user_email: str, custom_prompt: str, is_active: bool
    ) -> IAHUserPrompt:
        user_record = await self.session.execute(
            select(User).where(User.email == user_email)
        )
        user: User = user_record.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        #  then check if the custom record already existing for the given user
        custom_prompt_record = await self.session.execute(
            select(IAHUserPrompt).where(IAHUserPrompt.user_id == user.id)
        )

        user_custom_prompt: IAHUserPrompt = custom_prompt_record.scalar_one_or_none()

        if user_custom_prompt is None:
            # create a new custom prompt
            new_custom_prompt = IAHUserPrompt(
                user_id=user.id, is_active=is_active, user_prompt=custom_prompt
            )

            self.session.add(new_custom_prompt)
            await self.session.commit()

            return new_custom_prompt

        else:
            user_custom_prompt.is_active = is_active
            user_custom_prompt.user_prompt = custom_prompt

            self.session.add(user_custom_prompt)
            await self.session.commit()

            return custom_prompt

    async def get_user_iah_custom_prompt(self, user_email: str) -> IAHUserPrompt:
        user_record = await self.session.execute(
            select(User).where(User.email == user_email)
        )
        user: User = user_record.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        custom_prompt_record = await self.session.execute(
            select(IAHUserPrompt).where(IAHUserPrompt.user_id == user.id)
        )

        custom_prompt: IAHUserPrompt = custom_prompt_record.scalar_one_or_none()

        return custom_prompt

    async def create_or_update_sra_user_custom_prompt(
        self, user_email: str, custom_prompt: str, is_active: bool
    ) -> SRAUserPrompt:
        user_record = await self.session.execute(
            select(User).where(User.email == user_email)
        )
        user: User = user_record.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        #  then check if the custom record already existing for the given user
        custom_prompt_record = await self.session.execute(
            select(SRAUserPrompt).where(SRAUserPrompt.user_id == user.id)
        )

        user_custom_prompt: SRAUserPrompt = custom_prompt_record.scalar_one_or_none()

        if user_custom_prompt is None:
            # create a new custom prompt
            new_custom_prompt = SRAUserPrompt(
                user_id=user.id, is_active=is_active, user_prompt=custom_prompt
            )

            self.session.add(new_custom_prompt)
            await self.session.commit()

            return new_custom_prompt

        else:
            user_custom_prompt.is_active = is_active
            user_custom_prompt.user_prompt = custom_prompt

            self.session.add(user_custom_prompt)
            await self.session.commit()

            return custom_prompt

    async def get_user_sra_custom_prompt(self, user_email: str) -> SRAUserPrompt:
        user_record = await self.session.execute(
            select(User).where(User.email == user_email)
        )
        user: User = user_record.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        custom_prompt_record = await self.session.execute(
            select(SRAUserPrompt).where(SRAUserPrompt.user_id == user.id)
        )

        custom_prompt: SRAUserPrompt = custom_prompt_record.scalar_one_or_none()

        return custom_prompt
