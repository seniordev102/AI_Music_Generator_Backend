from typing import List

from fastapi import Depends, HTTPException, status
from pydantic import UUID4
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import db_session
from app.models import SubscriptionConfiguration
from app.schemas import CreateSubscriptionConfig, UpdateSubscriptionConfig


class SubscriptionConfigService:
    def __init__(
        self,
        session: AsyncSession = Depends(db_session),
    ) -> None:
        self.session = session

    async def get_all_plans(self) -> List[SubscriptionConfiguration]:
        subscription_records = await self.session.execute(
            select(SubscriptionConfiguration)
        )
        subscriptions = subscription_records.scalars().all()
        return subscriptions

    async def seed_all_subscription_configs(self) -> List[SubscriptionConfiguration]:

        # create subscription config records
        free_subscription = SubscriptionConfiguration(
            subscription_name="SPARK",
            description="For individuals just getting started with the iah.fit platform",
            cover_image=None,
            monthly_price=0,
            yearly_price=0,
            is_active=True,
            stripe_monthly_product_id="free_monthly",
            stripe_yearly_product_id="free_yearly",
            stripe_monthly_price_id="free_monthly",
            stripe_yearly_price_id="free_yearly",
            numbers_of_ask_iah_queries=100,
            numbers_of_craft_my_sonics=10,
            numbers_of_sonic_supplement_shuffles=100,
            numbers_of_super_sonic_shuffles=100,
            numbers_of_ask_iah_playlist_generation=10,
            numbers_of_ask_iah_image_generation=10,
        )

        is_free_subscription_exists = await self.check_subscription_config_exists(
            free_subscription
        )

        if not is_free_subscription_exists:
            print("Creating free subscription")
            await self.create_subscription_config(free_subscription)
        else:
            print("Free subscription already exists")

        stripe_monthly_product_id = ""
        stripe_yearly_product_id = ""
        stripe_monthly_price_id = ""
        stripe_yearly_price_id = ""

        if settings.APP_ENV == "development":
            stripe_monthly_product_id = "prod_Q9756OzUXoYgyM"
            stripe_yearly_product_id = "prod_Q976WZUmvV62AM"
            stripe_monthly_price_id = "price_1PIorAIsB10kFhKoVjED6LbT"
            stripe_yearly_price_id = "price_1PIos5IsB10kFhKoWQXQFMAF"
        else:
            stripe_monthly_product_id = "prod_QHROkmuGhaJfBp"
            stripe_yearly_product_id = "prod_QHRS8dywoyyOw8"
            stripe_monthly_price_id = "price_1PQsXsF8KEZSCnqOrNXraWcw"
            stripe_yearly_price_id = "price_1PQsZHF8KEZSCnqO6XzkbPiJ"

        premium_subscription = SubscriptionConfiguration(
            subscription_name="IAH PREMIUM",
            description="Radiate Your Essence",
            cover_image="https://iah.fit/wp-content/uploads/2024/05/Premium.png",
            monthly_price=14.97,
            yearly_price=125,
            is_active=True,
            stripe_monthly_product_id=stripe_monthly_product_id,
            stripe_yearly_product_id=stripe_yearly_product_id,
            stripe_monthly_price_id=stripe_monthly_price_id,
            stripe_yearly_price_id=stripe_yearly_price_id,
            numbers_of_ask_iah_queries=1000,
            numbers_of_craft_my_sonics=1000,
            numbers_of_sonic_supplement_shuffles=5000,
            numbers_of_super_sonic_shuffles=5000,
            numbers_of_ask_iah_playlist_generation=1000,
            numbers_of_ask_iah_image_generation=1000,
        )

        is_premium_subscription_exists = await self.check_subscription_config_exists(
            premium_subscription
        )

        if not is_premium_subscription_exists:
            print("Creating iah premium subscription")
            await self.create_subscription_config(premium_subscription)
        else:
            print("iah premium subscription already exists")

        # get all subscription config records
        subscription_records = await self.session.execute(
            select(SubscriptionConfiguration)
        )
        subscriptions = subscription_records.scalars().all()
        return subscriptions

    async def check_subscription_config_exists(
        self, config_data: CreateSubscriptionConfig
    ):

        config_records_query = await self.session.execute(
            select(SubscriptionConfiguration).where(
                or_(
                    SubscriptionConfiguration.stripe_monthly_product_id
                    == config_data.stripe_monthly_product_id,
                    SubscriptionConfiguration.stripe_yearly_product_id
                    == config_data.stripe_yearly_product_id,
                )
            )
        )
        config_records = config_records_query.scalars().all()

        if config_records:
            return True
        else:
            return False

    async def create_subscription_config(self, config_data: CreateSubscriptionConfig):

        config_records = await self.check_subscription_config_exists(config_data)

        if config_records:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stripe plan already exists for monthly or yearly subscription",
            )

        # create a new subscription config record
        new_subscription_config = SubscriptionConfiguration(**config_data.dict())
        self.session.add(new_subscription_config)
        await self.session.commit()
        await self.session.refresh(new_subscription_config)

        return new_subscription_config

    async def update_subscription_config(
        self, config_id: UUID4, config_data: UpdateSubscriptionConfig
    ):

        config_records = await self.session.execute(
            select(SubscriptionConfiguration).where(
                SubscriptionConfiguration.id == config_id
            )
        )

        subscription_config = config_records.scalar_one_or_none()

        if not subscription_config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Subscription config not found",
            )

        # update subscription config record
        for field, value in config_data.dict().items():
            if value is not None:
                setattr(subscription_config, field, value)

            self.session.add(subscription_config)
            await self.session.commit()
            await self.session.refresh(subscription_config)

        return subscription_config

    async def get_subscription_config_by_stripe_price_id(
        self, stripe_price_id: str
    ) -> SubscriptionConfiguration:
        config_records = await self.session.execute(
            select(SubscriptionConfiguration).where(
                or_(
                    SubscriptionConfiguration.stripe_monthly_price_id
                    == stripe_price_id,
                    SubscriptionConfiguration.stripe_yearly_price_id == stripe_price_id,
                )
            )
        )

        subscription_config = config_records.scalar_one_or_none()
        return subscription_config
