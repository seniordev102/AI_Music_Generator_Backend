from datetime import datetime

from fastapi import Depends, HTTPException, UploadFile, status
from pydantic import UUID4
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.http_response_model import PageMeta
from app.common.s3_file_upload import S3FileClient
from app.common.utils import resize_image
from app.config import settings
from app.database import db_session
from app.models import Collection, Track
from app.schemas import CreateCollection, UpdateCollection


class CollectionService:
    def __init__(self, session: AsyncSession = Depends(db_session)) -> None:
        self.session = session

    # get all collections
    async def get_all_collections(self, page: int, page_size: int) -> list[Collection]:
        collections_to_skip = (page - 1) * page_size

        # Get total number of items
        total_items = await self.session.execute(
            select(func.count()).select_from(Collection)
        )
        total_items = total_items.scalar()

        # Calculate total pages
        total_pages = -(-total_items // page_size)

        # Fetch paginated items
        collection_list = await self.session.execute(
            select(Collection)
            .where(Collection.is_active == True)
            .where(Collection.is_private != True)
            .where(or_(Collection.is_delist == False, Collection.is_delist.is_(None)))
            .offset(collections_to_skip)
            .order_by(Collection.order_seq.asc())
            .limit(page_size)
        )
        collections = collection_list.scalars().fetchall()

        return collections, PageMeta(
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            total_items=total_items,
        )

    async def get_all_collections_with_one_track(self):
        # Fetch all collections with filters
        collections_query = (
            select(Collection)
            .where(Collection.is_active == True)
            .where(Collection.is_private != True)
            .where(or_(Collection.is_delist == False, Collection.is_delist.is_(None)))
            .order_by(Collection.order_seq.asc())
        )

        collection_result = await self.session.execute(collections_query)
        collections = collection_result.scalars().fetchall()

        collection_data = []
        # For each collection, get one random track
        for collection in collections:
            random_track = await self.session.execute(
                select(Track)
                .where(Track.collection_id == collection.id)
                .where(Track.is_private != True)
                .order_by(func.random())
                .limit(1)
            )
            track = random_track.scalar_one_or_none()
            collection_data.append(
                {
                    "collection": collection,
                    "track": track,
                }
            )

        return collection_data

    async def get_all_collections_for_admin(
        self, page: int, page_size: int
    ) -> list[Collection]:
        collections_to_skip = (page - 1) * page_size

        # Get total number of items
        total_items = await self.session.execute(
            select(func.count()).select_from(Collection)
        )
        total_items = total_items.scalar()

        # Calculate total pages
        total_pages = -(-total_items // page_size)

        # Fetch paginated items
        collection_list = await self.session.execute(
            select(Collection)
            .offset(collections_to_skip)
            .order_by(Collection.order_seq.asc())
            .limit(page_size)
        )
        collections = collection_list.scalars().fetchall()

        return collections, PageMeta(
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            total_items=total_items,
        )

    # get an collection by id
    async def get_collection_by_id(self, id: UUID4) -> Collection:
        collection_record = await self.session.execute(
            select(Collection).where(Collection.id == id)
        )
        collection = collection_record.scalar_one_or_none()

        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found"
            )

        return collection

    # create a collection
    async def create_collection(
        self,
        cover_image_file: UploadFile,
        square_cover_image_file: UploadFile,
        data: CreateCollection,
    ) -> Collection:

        s3_client_service = S3FileClient()
        if cover_image_file:

            file_content = await cover_image_file.read()
            cover_image_url = s3_client_service.upload_file_if_not_exists(
                folder_name="collection",
                file_name=cover_image_file.filename,
                file_content=file_content,
                content_type=cover_image_file.content_type,
            )

            # square cover image file upload handler
            if square_cover_image_file:
                square_file_content = await square_cover_image_file.read()
                square_cover_image_url = s3_client_service.upload_file_if_not_exists(
                    folder_name="collection",
                    file_name=square_cover_image_file.filename,
                    file_content=square_file_content,
                    content_type=square_cover_image_file.content_type,
                )

                # resize the image to thumbnail size
                resized_image_data = await resize_image(
                    file_content=square_file_content,
                    file_name=square_cover_image_file.filename,
                    file_content_type=square_cover_image_file.content_type,
                    height=settings.THUMBNAIL_HEIGHT,
                    width=settings.THUMBNAIL_WIDTH,
                )

                # upload the thumbnail to s3 bucket and get the url
                square_thumbnail_uploaded_url = (
                    s3_client_service.upload_file_if_not_exists(
                        folder_name="collection",
                        file_name=resized_image_data["file_name"],
                        file_content=resized_image_data["image_content"],
                        content_type=resized_image_data["file_content_type"],
                    )
                )

                # set the urls into collection data
                data.square_cover_image = square_cover_image_url
                data.square_thumbnail_image = square_thumbnail_uploaded_url

            resized_image_data = await resize_image(
                file_content=file_content,
                file_name=cover_image_file.filename,
                file_content_type=cover_image_file.content_type,
                height=settings.THUMBNAIL_HEIGHT,
                width=settings.THUMBNAIL_WIDTH,
            )

            # upload the thumbnail to s3 bucket and get the url
            thumbnail_uploaded_url = s3_client_service.upload_file_if_not_exists(
                folder_name="collection",
                file_name=resized_image_data["file_name"],
                file_content=resized_image_data["image_content"],
                content_type=resized_image_data["file_content_type"],
            )

            data.cover_image = cover_image_url
            data.thumbnail_image = thumbnail_uploaded_url
            data.ipfs_cover_image = None
            data.ipfs_thumbnail_image = None

        if not data.order_seq:
            #  get the current count of collections
            collection_count = await self.session.execute(
                select(func.count()).select_from(Collection)
            )
            data.order_seq = collection_count.scalar() + 1

        collection = Collection(**data.dict())
        self.session.add(collection)
        await self.session.commit()
        await self.session.refresh(collection)

        return collection

    # update the collection
    async def update_collection(
        self,
        id: UUID4,
        data: UpdateCollection,
        cover_image_file: UploadFile,
        square_cover_image_file: UploadFile,
    ) -> Collection:
        collection_record = await self.session.execute(
            select(Collection).where(Collection.id == id)
        )
        collection: Collection = collection_record.scalar_one_or_none()

        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found"
            )

        if cover_image_file:
            #  upload the file to s3 bucket and get the url
            file_content = await cover_image_file.read()

            # compress and reduce the file size for the thumbnail
            s3_client = S3FileClient()
            cover_image_url = s3_client.upload_file_if_not_exists(
                folder_name="collection",
                file_name=cover_image_file.filename,
                file_content=file_content,
                content_type=cover_image_file.content_type,
            )

            # create the thumbnail version of the image
            resized_image_data = await resize_image(
                file_content=file_content,
                file_name=cover_image_file.filename,
                file_content_type=cover_image_file.content_type,
                height=settings.THUMBNAIL_HEIGHT,
                width=settings.THUMBNAIL_WIDTH,
            )

            # upload the thumbnail to s3 bucket and get the url
            thumbnail_uploaded_url = s3_client.upload_file_if_not_exists(
                folder_name="collection",
                file_name=resized_image_data["file_name"],
                file_content=resized_image_data["image_content"],
                content_type=resized_image_data["file_content_type"],
            )

            data.cover_image = cover_image_url
            data.thumbnail_image = thumbnail_uploaded_url
            data.ipfs_cover_image = None
            data.ipfs_thumbnail_image = None

        if square_cover_image_file:
            #  upload the file to s3 bucket and get the url
            square_file_content = await square_cover_image_file.read()

            # compress and reduce the file size for the thumbnail
            s3_client = S3FileClient()
            square_cover_image_url = s3_client.upload_file_if_not_exists(
                folder_name="collection",
                file_name=square_cover_image_file.filename,
                file_content=square_file_content,
                content_type=square_cover_image_file.content_type,
            )

            # create the thumbnail version of the image
            resized_image_data = await resize_image(
                file_content=square_file_content,
                file_name=square_cover_image_file.filename,
                file_content_type=square_cover_image_file.content_type,
                height=settings.THUMBNAIL_HEIGHT,
                width=settings.THUMBNAIL_WIDTH,
            )

            # upload the thumbnail to s3 bucket and get the url
            square_thumbnail_uploaded_url = s3_client.upload_file_if_not_exists(
                folder_name="collection",
                file_name=resized_image_data["file_name"],
                file_content=resized_image_data["image_content"],
                content_type=resized_image_data["file_content_type"],
            )

            data.square_cover_image = square_cover_image_url
            data.square_thumbnail_image = square_thumbnail_uploaded_url

        # Step 1: Explicitly update the updated_at field
        data.updated_at = datetime.utcnow()

        # Step 2: Update the fields with new values
        for field, value in data.dict().items():
            if (
                value is not None
            ):  # Only update if the field was provided in the request
                setattr(collection, field, value)

        # Step 3: Update track records based on collection's is_hidden and is_private values
        if "is_hidden" in data.dict() or "is_private" in data.dict():
            await self.session.execute(
                update(Track)
                .where(Track.collection_id == collection.id)
                .values(
                    is_hidden=collection.is_hidden, is_private=collection.is_private
                )
            )

        # Step 4: Commit the changes
        self.session.add(collection)
        await self.session.commit()

        return collection

    # delete the collection
    async def delete_collection(self, id: UUID4) -> bool:
        collection_record = await self.session.execute(
            select(Collection).where(Collection.id == id)
        )
        collection = collection_record.scalar_one_or_none()

        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found"
            )

        # delete all the tracks of the collection
        tracks_records = await self.session.execute(
            select(Track).where(Track.collection_id == id)
        )
        tracks = tracks_records.scalars().fetchall()
        for track in tracks:
            await self.session.delete(track)

        # delete the collection
        await self.session.delete(collection)
        await self.session.commit()

        return True

    async def get_tracks_of_collection(self, collection_id: UUID4) -> bool:

        # Get total number of items
        tracks_records = await self.session.execute(
            select(Track)
            # Add this line to join
            .join(Collection, Collection.id == Track.collection_id)
            .where(Collection.id == collection_id)
            .where(Track.is_private != True)
            .order_by(Track.order_seq.asc())
        )
        tracks = tracks_records.scalars().fetchall()

        return tracks

    async def search_collections(self, query: str):
        search_query = f"%{query}%"  # Format the query for a LIKE search
        result = await self.session.execute(
            select(Collection).where(
                or_(
                    Collection.name.ilike(search_query),
                    Collection.description.ilike(search_query),
                    Collection.short_description.ilike(search_query),
                )
            )
        )
        results = result.scalars().fetchall()

        return results
