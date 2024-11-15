from typing import List, Union

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import db_session
from app.models import User
from app.schemas import UpdateUser
from app.stripe.stripe_service import StripeService


class SubscriptionService:
    def __init__(
        self,
        # auth_handler: AuthHandler = AuthHandler(),
        session: AsyncSession = Depends(db_session),
        stripe_service=StripeService(),
    ) -> None:
        self.session = session
        self.stripe_service = stripe_service

    async def get_all_plans(self) -> List:
        plans = self.stripe_service.get_subscription_plans()
        return plans.data

    async def delete_stripe_customer_id(self, email: str):
        # get user by email
        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: Union[User, None] = user_record.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        user.stripe_customer_id = None
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return True

    async def add_stripe_customer_id(self, email: str, stripe_customer_id: str):
        # get user by email
        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: Union[User, None] = user_record.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        user.stripe_customer_id = stripe_customer_id
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return True

    async def update_user_subscription(self, user_subscription: UpdateUser):

        # # get user by stripe customer id
        user_record = await self.session.execute(
            select(User).where(
                User.stripe_customer_id == user_subscription.stripe_customer_id
            )
        )
        user: Union[User, None] = user_record.scalar_one_or_none()

        if user is None:
            print("user is None")
        else:
            for field, value in user_subscription.dict().items():
                if value is not None:
                    if value == "null" or value == "":
                        value = None
                    setattr(user, field, value)

            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)

        return True

    async def get_user_subscription(self, email: str):
        # get user by email
        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: Union[User, None] = user_record.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        return {"user": user}
