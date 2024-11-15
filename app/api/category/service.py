from datetime import datetime
from typing import List

from fastapi import Depends, HTTPException, UploadFile, status
from pydantic import UUID4
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.http_response_model import PageMeta
from app.common.s3_file_upload import S3FileClient
from app.database import db_session
from app.models import Category, Collection, Track
from app.schemas import CreateCategory, UpdateCollection


class CategoryService:
    def __init__(self, session: AsyncSession = Depends(db_session)) -> None:
        self.session = session

    # get all categories
    async def get_all_categories(self, page: int, page_size: int) -> list[Category]:
        categories_to_skip = (page - 1) * page_size

        # Get total number of items
        total_items = await self.session.execute(
            select(func.count()).select_from(Category)
        )
        total_items = total_items.scalar()

        # Calculate total pages
        total_pages = -(-total_items // page_size)

        # Fetch paginated items
        category_list = await self.session.execute(
            select(Category)
            .where(Category.is_active == True)
            .offset(categories_to_skip)
            .order_by(Category.order_seq.asc())
            .limit(page_size)
        )
        categories = category_list.scalars().fetchall()

        return categories, PageMeta(
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            total_items=total_items,
        )

    # get an collection by id
    async def get_category_by_id(self, id: UUID4) -> Category:
        category_record = await self.session.execute(
            select(Category).where(Category.id == id)
        )
        category = category_record.scalar_one_or_none()

        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
            )

        return category

    # create a category
    async def create_category(
        self, cover_image_file: UploadFile, data: CreateCategory
    ) -> Category:

        s3_client_service = S3FileClient()
        if cover_image_file:
            file_content = await cover_image_file.read()
            cover_image_url = s3_client_service.upload_file_if_not_exists(
                folder_name="category",
                file_name=cover_image_file.filename,
                file_content=file_content,
                content_type=cover_image_file.content_type,
            )
            data.cover_image = cover_image_url

        if not data.order_seq:
            #  get the current count of category
            category_count = await self.session.execute(
                select(func.count()).select_from(Category)
            )
            data.order_seq = category_count.scalar() + 1

        category = Category(**data.dict())
        self.session.add(category)
        await self.session.commit()
        await self.session.refresh(category)

        return category

    # update the category
    async def update_category(
        self,
        id: UUID4,
        cover_image_file: UploadFile,
        data: UpdateCollection,
    ) -> Category:
        category_record = await self.session.execute(
            select(Category).where(Category.id == id)
        )
        category = category_record.scalar_one_or_none()

        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
            )

        if cover_image_file:
            #  upload the file to s3 bucket and get the url
            file_content = await cover_image_file.read()

            # compress and reduce the file size for the thumbnail
            s3_client = S3FileClient()
            cover_image_url = s3_client.upload_file_if_not_exists(
                folder_name="category",
                file_name=cover_image_file.filename,
                file_content=file_content,
                content_type=cover_image_file.content_type,
            )
            data.cover_image = cover_image_url

        # Step 1: Explicitly update the updated_at field
        data.updated_at = datetime.utcnow()

        # Step 2: Update the fields with new values
        for field, value in data.dict().items():
            if (
                value is not None
            ):  # Only update if the field was provided in the request
                setattr(category, field, value)

        # Step 3: Commit the changes
        self.session.add(category)
        await self.session.commit()

        return category

    # delete the category
    async def delete_category(self, id: UUID4) -> bool:
        category_record = await self.session.execute(
            select(Category).where(Category.id == id)
        )
        category = category_record.scalar_one_or_none()

        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
            )

        # delete the category
        await self.session.delete(category)
        await self.session.commit()

        return True

    # get all the collections belonging to a category
    async def get_collections_by_category(self, category_id: UUID4) -> list[Collection]:
        category_record = await self.session.execute(
            select(Category).where(Category.id == category_id)
        )
        category: Category = category_record.scalar_one_or_none()

        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
            )

        if category.collection_ids is None:
            return []
        else:
            collection_ids = category.collection_ids.split(",")
            collection_list = await self.session.execute(
                select(Collection)
                .where(Collection.id.in_(collection_ids))
                .order_by(Collection.order_seq.asc())
            )
            collections = collection_list.scalars().fetchall()

            return collections

    async def get_all_collections_belongs_to_all_categories(self) -> list[Collection]:
        all_collections = []
        # get all categories
        query = select(Category).where(Category.is_active == True)
        categories = await self.session.execute(query)
        categories = categories.scalars().fetchall()

        for category in categories:
            collections = await self.get_collections_by_category(
                category_id=category.id
            )
            all_collections.extend(collections)

        return all_collections

    async def get_random_tracks_based_on_category(
        self, category_id: UUID4, count: int
    ) -> List[dict]:

        # get collections belonging to the category
        collections = await self.get_collections_by_category(category_id)
        collection_ids = [str(collection.id) for collection in collections]

        track_records = await self.session.execute(
            select(Track, Collection)
            .where(Track.collection_id.in_(collection_ids))
            # Manual join condition
            .join(Collection, Track.collection_id == Collection.id)
            .order_by(func.random())
            .limit(count)
        )
        results = track_records.all()

        # Create a list of dictionaries with track and collection details
        tracks_with_collections = [
            {"track": track, "collection": collection} for track, collection in results
        ]

        # Check if we found enough tracks
        if not tracks_with_collections or len(tracks_with_collections) < count:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Could not find {count} random tracks",
            )

        return tracks_with_collections
