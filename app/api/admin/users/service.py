from fastapi import Depends
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.http_response_model import PageMeta
from app.database import db_session
from app.models import User


class AdminUserService:
    def __init__(
        self,
        session: AsyncSession = Depends(db_session),
    ) -> None:
        self.session = session

    async def get_all_user_details(
        self,
        page: int,
        per_page: int,
        search: str,
        sort_column: str = "created_at",
        sort_direction: str = "desc",
    ):
        users_to_skip = (page - 1) * per_page

        # Define the mapping of sort columns to actual User model columns
        sort_column_mapping = {
            "name": User.name,
            "email": User.email,
            "subscription_plan": User.subscription_plan,
            "subscription_status": User.subscription_status,
            "created_at": User.created_at,
        }

        # Ensure the sort column is valid
        if sort_column not in sort_column_mapping:
            sort_column = "created_at"

        # Determine sort direction
        if sort_direction == "asc":
            order_by_clause = asc(sort_column_mapping[sort_column])
        else:
            order_by_clause = desc(sort_column_mapping[sort_column])

        # Get total number of items
        total_users_query = select(func.count()).select_from(User)
        if search:
            search_filter = or_(
                User.name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.subscription_status.ilike(f"%{search}%"),
                User.subscription_plan.ilike(f"%{search}%"),
            )
            total_users_query = total_users_query.where(search_filter)

        total_users = await self.session.execute(total_users_query)
        total_user_count = total_users.scalar()

        # Calculate total pages
        total_pages = -(-total_user_count // per_page)

        # Fetch paginated items
        user_query = (
            select(User).offset(users_to_skip).order_by(order_by_clause).limit(per_page)
        )

        if search:
            user_query = user_query.where(search_filter)

        user_list = await self.session.execute(user_query)
        users = user_list.scalars().fetchall()

        return users, PageMeta(
            page=page,
            page_size=per_page,
            total_pages=total_pages,
            total_items=total_user_count,
        )
