from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import db_session
from app.models import User


class DashboardStatService:
    def __init__(
        self,
        session: AsyncSession = Depends(db_session),
    ) -> None:
        self.session = session

    async def get_all_dashboard_stats(self):
        #  get all user counts
        register_user_count = await self.session.execute(select(func.count(User.id)))

        FUNDING_MEMBER_CODE = "528528"
        TEAM_MEMBER_CODE = "369369"

        founding_member_count = await self.session.execute(
            select(func.count(User.id)).where(User.invite_code == FUNDING_MEMBER_CODE)
        )

        team_member_count = await self.session.execute(
            select(func.count(User.id)).where(User.invite_code == TEAM_MEMBER_CODE)
        )

        subscribers_count = await self.session.execute(
            select(func.count(User.id)).where(User.subscription_plan != "free")
        )

        total_image_generations = await self.session.execute(
            select(func.sum(User.numbers_of_ask_iah_image_generation))
        )

        total_user_queries = await self.session.execute(
            select(func.sum(User.numbers_of_ask_iah_queries))
        )

        total_sonic_supplements_generations = await self.session.execute(
            select(func.sum(User.numbers_of_sonic_supplement_shuffles))
        )

        total_craft_my_sonic_generations = await self.session.execute(
            select(func.sum(User.numbers_of_craft_my_sonics))
        )

        return {
            "register_user_count": register_user_count.scalar(),
            "founding_member_count": founding_member_count.scalar(),
            "team_member_count": team_member_count.scalar(),
            "subscribers_count": subscribers_count.scalar(),
            "total_image_generations": total_image_generations.scalar(),
            "total_user_queries": total_user_queries.scalar(),
            "total_sonic_supplements_generations": total_sonic_supplements_generations.scalar(),
            "total_craft_my_sonic_generations": total_craft_my_sonic_generations.scalar(),
        }
