from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import db_session
from app.models import SystemExcludeMusicCategory, User
from app.schemas import CreateExcludeCategory


class CategoryManageService:
    def __init__(
        self,
        session: AsyncSession = Depends(db_session),
    ) -> None:
        self.session = session

    async def get_exclude_categories_by_type_service(self, exclude_type: str):
        query = select(SystemExcludeMusicCategory).where(
            SystemExcludeMusicCategory.exclude_type == exclude_type
        )
        result = await self.session.execute(query)
        record = result.scalars().first()
        return record

    async def exclude_categories_from_iah_service(self, data: CreateExcludeCategory):
        # check if the record exists for given category type
        query = select(SystemExcludeMusicCategory).where(
            SystemExcludeMusicCategory.exclude_type == data.exclude_type
        )
        result = await self.session.execute(query)
        record: CreateExcludeCategory = result.scalars().first()

        category_id_str = ",".join(data.category_ids)

        if record:
            # update the record
            record.category_ids = category_id_str
        else:
            # create a new record
            record = SystemExcludeMusicCategory(
                exclude_type=data.exclude_type,
                category_ids=category_id_str,
            )
            self.session.add(record)

        await self.session.commit()
        return record
