from datetime import datetime

from fastapi import Depends, HTTPException, UploadFile, status
from pydantic import UUID4
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.http_response_model import PageMeta
from app.common.s3_file_upload import S3FileClient
from app.common.utils import resize_image
from app.config import settings
from app.database import db_session
from app.models import Collection, SonicSupplements, Track
from app.schemas import CreateSonicSupplement, UpdateSonicSupplement


class SonicSupplementService:
    def __init__(self, session: AsyncSession = Depends(db_session)) -> None:
        self.session = session

    # get all collections
    async def get_all_sonic_supplement_collections(
        self, page: int, page_size: int
    ) -> list[SonicSupplements]:
        collections_to_skip = (page - 1) * page_size

        # Get total number of items
        total_items = await self.session.execute(
            select(func.count()).select_from(SonicSupplements)
        )
        total_items = total_items.scalar()

        # Calculate total pages
        total_pages = -(-total_items // page_size)

        # Fetch paginated items
        collection_list = await self.session.execute(
            select(SonicSupplements)
            .offset(collections_to_skip)
            .order_by(SonicSupplements.order_seq.asc())
            .limit(page_size)
        )
        sonic_supplement_collections = collection_list.scalars().fetchall()

        return sonic_supplement_collections, PageMeta(
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            total_items=total_items,
        )

    # get an collection by id
    async def get_sonic_supplement_collection_by_id(
        self, id: UUID4
    ) -> SonicSupplements:
        collection_record = await self.session.execute(
            select(SonicSupplements).where(SonicSupplements.id == id)
        )
        sonic_supplement_collection = collection_record.scalar_one_or_none()

        if not sonic_supplement_collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sonic Supplement Collection not found",
            )

        return sonic_supplement_collection

    # create a collection
    async def create_sonic_supplement_collection(
        self,
        cover_image_file: UploadFile,
        square_cover_image_file: UploadFile,
        data: CreateSonicSupplement,
    ) -> SonicSupplements:

        s3_client_service = S3FileClient()
        if cover_image_file:

            file_content = await cover_image_file.read()
            cover_image_url = s3_client_service.upload_file_if_not_exists(
                folder_name="sonic_supplement_collection",
                file_name=cover_image_file.filename,
                file_content=file_content,
                content_type=cover_image_file.content_type,
            )

            resized_image_data = await resize_image(
                file_content=file_content,
                file_name=cover_image_file.filename,
                file_content_type=cover_image_file.content_type,
                height=settings.THUMBNAIL_HEIGHT,
                width=settings.THUMBNAIL_WIDTH,
            )

            # upload the thumbnail to s3 bucket and get the url
            thumbnail_uploaded_url = s3_client_service.upload_file_if_not_exists(
                folder_name="sonic_supplement_collection",
                file_name=resized_image_data["file_name"],
                file_content=resized_image_data["image_content"],
                content_type=resized_image_data["file_content_type"],
            )

            data.cover_image = cover_image_url
            data.cover_thumbnail_image = thumbnail_uploaded_url

        if square_cover_image_file:

            file_content = await square_cover_image_file.read()
            square_cover_image_url = s3_client_service.upload_file_if_not_exists(
                folder_name="sonic_supplement_collection",
                file_name=square_cover_image_file.filename,
                file_content=file_content,
                content_type=square_cover_image_file.content_type,
            )

            resized_image_data = await resize_image(
                file_content=file_content,
                file_name=square_cover_image_file.filename,
                file_content_type=square_cover_image_file.content_type,
                height=settings.THUMBNAIL_HEIGHT,
                width=settings.THUMBNAIL_WIDTH,
            )

            # upload the thumbnail to s3 bucket and get the url
            square_thumbnail_uploaded_url = s3_client_service.upload_file_if_not_exists(
                folder_name="sonic_supplement_collection",
                file_name=resized_image_data["file_name"],
                file_content=resized_image_data["image_content"],
                content_type=resized_image_data["file_content_type"],
            )

            data.square_cover_image = square_cover_image_url
            data.square_thumbnail_image = square_thumbnail_uploaded_url

        if not data.order_seq:
            #  get the current count of collections
            collection_count = await self.session.execute(
                select(func.count()).select_from(SonicSupplements)
            )
            data.order_seq = collection_count.scalar() + 1

        sonic_supplement_collection = SonicSupplements(**data.dict())
        self.session.add(sonic_supplement_collection)
        await self.session.commit()
        await self.session.refresh(sonic_supplement_collection)

        return sonic_supplement_collection

    # update the collection

    async def update_sonic_supplement_collection_collection(
        self,
        id: UUID4,
        data: UpdateSonicSupplement,
        cover_image_file: UploadFile,
        square_cover_image_file: UploadFile,
    ) -> SonicSupplements:
        collection_record = await self.session.execute(
            select(SonicSupplements).where(SonicSupplements.id == id)
        )
        sonic_supplement_collection = collection_record.scalar_one_or_none()

        if not sonic_supplement_collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sonic Supplement Collection not found",
            )

        if cover_image_file:
            #  upload the file to s3 bucket and get the url
            file_content = await cover_image_file.read()

            # compress and reduce the file size for the thumbnail
            s3_client = S3FileClient()
            cover_image_url = s3_client.upload_file_if_not_exists(
                folder_name="sonic_supplement_collection",
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
                folder_name="sonic_supplement_collection",
                file_name=resized_image_data["file_name"],
                file_content=resized_image_data["image_content"],
                content_type=resized_image_data["file_content_type"],
            )

            data.cover_image = cover_image_url
            data.cover_thumbnail_image = thumbnail_uploaded_url

        if square_cover_image_file:
            #  upload the file to s3 bucket and get the url
            file_content = await square_cover_image_file.read()

            # compress and reduce the file size for the thumbnail
            s3_client = S3FileClient()
            square_cover_image_url = s3_client.upload_file_if_not_exists(
                folder_name="sonic_supplement_collection",
                file_name=square_cover_image_file.filename,
                file_content=file_content,
                content_type=square_cover_image_file.content_type,
            )

            # create the thumbnail version of the image
            resized_image_data = await resize_image(
                file_content=file_content,
                file_name=square_cover_image_file.filename,
                file_content_type=square_cover_image_file.content_type,
                height=settings.THUMBNAIL_HEIGHT,
                width=settings.THUMBNAIL_WIDTH,
            )

            # upload the thumbnail to s3 bucket and get the url
            square_cover_thumbnail_uploaded_url = s3_client.upload_file_if_not_exists(
                folder_name="sonic_supplement_collection",
                file_name=resized_image_data["file_name"],
                file_content=resized_image_data["image_content"],
                content_type=resized_image_data["file_content_type"],
            )

            data.square_cover_image = square_cover_image_url
            data.square_thumbnail_image = square_cover_thumbnail_uploaded_url

        # Step 1: Explicitly update the updated_at field
        data.updated_at = datetime.utcnow()

        # Step 2: Update the fields with new values
        for field, value in data.dict().items():
            if (
                value is not None
            ):  # Only update if the field was provided in the request
                setattr(sonic_supplement_collection, field, value)

        # Step 3: Commit the changes
        self.session.add(sonic_supplement_collection)
        await self.session.commit()

        return sonic_supplement_collection

    # delete the sonic supplement collection
    async def delete_sonic_supplement_collection(self, id: UUID4) -> bool:
        collection_record = await self.session.execute(
            select(SonicSupplements).where(SonicSupplements.id == id)
        )
        sonic_supplement_collection = collection_record.scalar_one_or_none()

        if not sonic_supplement_collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sonic Supplement Collection not found",
            )

        # delete the Sonic Supplement collection
        await self.session.delete(SonicSupplements)
        await self.session.commit()

        return True

    # get all sonic supplement tracks
    async def get_all_sonic_supplement_tracks(
        self, sonic_supplement_id: UUID4
    ) -> list[dict]:
        # get track ids string from sonic supplement collection
        collection_record = await self.session.execute(
            select(SonicSupplements).where(SonicSupplements.id == sonic_supplement_id)
        )
        sonic_supplement_collection: SonicSupplements = (
            collection_record.scalar_one_or_none()
        )
        track_ids = sonic_supplement_collection.track_ids
        # convert string to list
        track_ids_list = track_ids.split(",")

        tracks = []
        try:
            # get all tracks based on id list
            tracks_record = await self.session.execute(
                select(Track)
                .filter(Track.id.in_(track_ids_list))
                .order_by(Track.order_seq.asc())
            )
            tracks = tracks_record.scalars().fetchall()
        except Exception:
            print(f"error while fetching tracks")

        # prepare response with collection details
        response = []
        for track in tracks:
            # Fetch collection details based on collection_id in track
            collection_record = await self.session.execute(
                select(Collection).where(Collection.id == track.collection_id)
            )
            collection = collection_record.scalar_one_or_none()

            # Add track and collection details to the response
            response.append(
                {
                    "track": track,  # or serialize the track object as per your needs
                    "collection": collection,  # or serialize the collection object as per your needs
                }
            )

        return response

    async def get_all_sonic_supplement_recommended_collections(
        self, id: UUID4
    ) -> list[SonicSupplements]:
        # get all sonic supplement collections expect provided id
        collection_records = await self.session.execute(
            select(SonicSupplements).where(SonicSupplements.id != id)
        )
        sonic_supplement_collections = collection_records.scalars().fetchall()
        return sonic_supplement_collections

    async def search_sonic_supplement_collections(self, query: str):
        search_query = f"%{query}%"  # Format the query for a LIKE search
        result = await self.session.execute(
            select(SonicSupplements).where(
                or_(
                    SonicSupplements.name.ilike(search_query),
                    SonicSupplements.description.ilike(search_query),
                    SonicSupplements.short_description.ilike(search_query),
                )
            )
        )
        results = result.scalars().fetchall()

        return results
