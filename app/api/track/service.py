import json
import uuid as uuid_pkg
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Depends, HTTPException, UploadFile, status
from pydantic import UUID4
from sqlalchemy import and_, asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.track.audio_analyzer import AudioAnalyzerService
from app.common.http_response_model import PageMeta
from app.common.s3_file_upload import S3FileClient
from app.common.utils import resize_image
from app.config import settings
from app.database import db_session
from app.models import Collection, Track
from app.schemas import CreateTrack, UpdateTrack


class TrackService:
    def __init__(
        self,
        session: AsyncSession = Depends(db_session),
        s3_client: S3FileClient = S3FileClient(),
    ) -> None:
        self.session = session
        self.s3_client = s3_client

    # get all tracks
    async def get_all_tracks(
        self,
        page: int,
        page_size: int,
        search: Optional[str] = None,
        is_lyrical: Optional[bool] = None,
        is_hidden: Optional[bool] = None,
        is_private: Optional[bool] = None,
        status_filter: Optional[str] = None,
        sort_by: Optional[str] = "created_at",
        sort_order: Optional[str] = "desc",
    ) -> tuple[list[Track], PageMeta]:
        tracks_to_skip = (page - 1) * page_size

        # Start building the query
        query = select(Track)

        # Add search conditions if search parameter is provided
        if search:
            search_str = f"%{search}%"
            query = query.where(
                or_(
                    Track.name.ilike(search_str),
                    Track.description.ilike(search_str),
                    Track.frequency.ilike(search_str),
                    Track.frequency_meaning.ilike(search_str),
                    Track.upright_message.ilike(search_str),
                )
            )

        # Add filter conditions
        filter_conditions = []
        if is_lyrical is not None:
            filter_conditions.append(Track.is_lyrical == is_lyrical)
        if is_hidden is not None:
            filter_conditions.append(Track.is_hidden == is_hidden)
        if is_private is not None:
            filter_conditions.append(Track.is_private == is_private)
        if status_filter:
            filter_conditions.append(Track.status == status_filter)

        if filter_conditions:
            query = query.where(and_(*filter_conditions))

        # Add sorting
        sort_column = getattr(Track, sort_by, Track.created_at)
        if sort_order.lower() == "asc":
            query = query.order_by(asc(sort_column))
        else:
            query = query.order_by(desc(sort_column))

        # Get total count for pagination
        count_query = select(func.count()).select_from(query.subquery())
        total_items = await self.session.execute(count_query)
        total_items = total_items.scalar()

        # Calculate total pages
        total_pages = -(-total_items // page_size)  # Ceiling division

        # Add pagination
        query = query.offset(tracks_to_skip).limit(page_size)

        # Execute the final query
        result = await self.session.execute(query)
        tracks = result.scalars().all()

        return tracks, PageMeta(
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            total_items=total_items,
        )

    # get a track by id
    async def get_track_by_id(self, id: UUID4) -> Track:
        track_record = await self.session.execute(select(Track).where(Track.id == id))
        track = track_record.scalar_one_or_none()

        if not track:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Track not found"
            )

        return track

    # get a track by id
    async def get_track__with_collection(self, id: UUID4) -> Track:
        track_record = await self.session.execute(select(Track).where(Track.id == id))
        track = track_record.scalar_one_or_none()

        if not track:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Track not found"
            )

        # Get the collection details
        collection_record = await self.session.execute(
            select(Collection).where(Collection.id == track.collection_id)
        )
        collection = collection_record.scalar_one_or_none()
        return {"track": track, "collection": collection}

    async def get_tracks_with_collections_by_id(
        self, track_ids: List[UUID4]
    ) -> List[Dict[str, Any]]:
        # Query for tracks
        tracks_query = select(Track).where(Track.id.in_(track_ids))
        tracks_result = await self.session.execute(tracks_query)
        tracks = tracks_result.scalars().all()

        # Check if all tracks were found
        if len(tracks) != len(track_ids):
            missing_ids = set(track_ids) - set(track.id for track in tracks)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tracks not found for IDs: {', '.join(str(id) for id in missing_ids)}",
            )

        # Get unique collection IDs
        collection_ids = set(track.collection_id for track in tracks)

        # Query for collections
        collections_query = select(Collection).where(Collection.id.in_(collection_ids))
        collections_result = await self.session.execute(collections_query)
        collections = {
            collection.id: collection
            for collection in collections_result.scalars().all()
        }

        # Combine tracks and collections
        result = []
        for track in tracks:
            collection = collections.get(track.collection_id)
            result.append({"track": track, "collection": collection})

        return result

    async def get_tracks_with_collections_by_ids_no_safe_check(
        self, track_ids: List[UUID4]
    ) -> List[Dict[str, Any]]:
        # Query for tracks
        tracks_query = select(Track).where(Track.id.in_(track_ids))
        tracks_result = await self.session.execute(tracks_query)
        tracks = tracks_result.scalars().all()

        # Create a dictionary of tracks keyed by their IDs
        tracks_dict = {track.id: track for track in tracks}

        # Get unique collection IDs
        collection_ids = set(track.collection_id for track in tracks)

        # Query for collections
        collections_query = select(Collection).where(Collection.id.in_(collection_ids))
        collections_result = await self.session.execute(collections_query)
        collections = {
            collection.id: collection
            for collection in collections_result.scalars().all()
        }

        # Combine tracks and collections in the original order
        result = []
        for track_id in track_ids:
            track = tracks_dict.get(track_id)
            if track:
                collection = collections.get(track.collection_id)
                result.append({"track": track, "collection": collection})

        return result

    # create a track
    async def create_track(self, track_data: CreateTrack) -> Track:

        try:

            is_valid_files = self.file_type_validator(
                instrumental_audio_file=track_data.instrumental_audio_file,
                upright_audio_file=track_data.upright_audio_file,
                reverse_audio_file=track_data.reverse_audio_file,
                hires_audio_file=track_data.hires_audio_file,
                cover_image_file=track_data.cover_image_file,
            )

            if not is_valid_files["is_valid"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=is_valid_files["message"],
                )

            # read all the uploaded file content
            instrumental_audio_file_content = (
                await track_data.instrumental_audio_file.read()
            )

            hires_audio_file_content = await track_data.hires_audio_file.read()
            cover_image_file_content = await track_data.cover_image_file.read()

            # extract the upright mp3 audio metadata
            audio_analyzer_service = AudioAnalyzerService()
            track_technical_data = await audio_analyzer_service.analyze(
                file_content=instrumental_audio_file_content,
                file_name=track_data.instrumental_audio_file.filename,
            )

            folder_name = f"tracks/{track_data.name}"

            instrumental_audio_url = self.s3_client.upload_file_if_not_exists(
                folder_name=folder_name,
                file_name=track_data.instrumental_audio_file.filename,
                file_content=instrumental_audio_file_content,
                content_type=track_data.instrumental_audio_file.content_type,
            )

            hires_audio_url = self.s3_client.upload_file_if_not_exists(
                folder_name=folder_name,
                file_name=track_data.hires_audio_file.filename,
                file_content=hires_audio_file_content,
                content_type=track_data.hires_audio_file.content_type,
            )

            cover_image_url = self.s3_client.upload_file_if_not_exists(
                folder_name=folder_name,
                file_name=track_data.cover_image_file.filename,
                file_content=cover_image_file_content,
                content_type=track_data.cover_image_file.content_type,
            )

            # create the thumbnail version of the image
            resized_image_data = await resize_image(
                file_content=cover_image_file_content,
                file_name=track_data.cover_image_file.filename,
                file_content_type=track_data.cover_image_file.content_type,
                height=settings.THUMBNAIL_HEIGHT,
                width=settings.THUMBNAIL_WIDTH,
            )

            # upload the thumbnail to s3 bucket and get the url
            thumbnail_uploaded_url = self.s3_client.upload_file_if_not_exists(
                folder_name=folder_name,
                file_name=resized_image_data["file_name"],
                file_content=resized_image_data["image_content"],
                content_type=resized_image_data["file_content_type"],
            )

            upright_audio_url = None
            reverse_audio_url = None

            if track_data.upright_audio_file:
                upright_audio_file_content = await track_data.upright_audio_file.read()
                upright_audio_url = self.s3_client.upload_file_if_not_exists(
                    folder_name=folder_name,
                    file_name=track_data.upright_audio_file.filename,
                    file_content=upright_audio_file_content,
                    content_type=track_data.upright_audio_file.content_type,
                )

            if track_data.reverse_audio_file:
                reverse_audio_file_content = await track_data.reverse_audio_file.read()
                reverse_audio_url = self.s3_client.upload_file_if_not_exists(
                    folder_name=folder_name,
                    file_name=track_data.reverse_audio_file.filename,
                    file_content=reverse_audio_file_content,
                    content_type=track_data.reverse_audio_file.content_type,
                )

            # process ipfs image upload
            ipfs_cover_image = None
            ipfs_thumbnail_image = None
            ipfs_instrumental_url = None
            ipfs_hires_url = None
            ipfs_upright_audio_url = None
            ipfs_reverse_audio_url = None

            # update track visibility based on collection data
            collection_record = await self.session.execute(
                select(Collection).where(Collection.id == track_data.collection_id)
            )

            collection: Collection = collection_record.scalar_one_or_none()

            # Create track record
            track_record = Track(
                collection_id=track_data.collection_id,
                user_id=track_data.user_id,
                name=track_data.name,
                instrumental_audio_url=instrumental_audio_url,
                upright_audio_url=upright_audio_url,
                reverse_audio_url=reverse_audio_url,
                hires_audio_url=hires_audio_url,
                cover_image=cover_image_url,
                thumbnail_image=thumbnail_uploaded_url,
                upright_message=track_data.upright_message,
                reverse_message=track_data.reverse_message,
                ipfs_cover_image=ipfs_cover_image,
                ipfs_thumbnail_image=ipfs_thumbnail_image,
                ipfs_instrumental_url=ipfs_instrumental_url,
                ipfs_hires_url=ipfs_hires_url,
                ipfs_upright_audio_url=ipfs_upright_audio_url,
                ipfs_reverse_audio_url=ipfs_reverse_audio_url,
                track_technical_data=track_technical_data,
                frequency=track_data.frequency,
                frequency_meaning=track_data.frequency_meaning,
                order_seq=track_data.order_seq,
                is_hidden=collection.is_hidden if collection else False,
                is_private=collection.is_private if collection else False,
                crafted_by=track_data.crafted_by,
            )

            self.session.add(track_record)
            await self.session.commit()
            return track_record

        except Exception as e:
            print(e)
            raise e

    def file_type_validator(
        self,
        instrumental_audio_file: UploadFile,
        hires_audio_file: UploadFile,
        upright_audio_file: UploadFile,
        reverse_audio_file: UploadFile,
        cover_image_file: UploadFile,
    ):
        if instrumental_audio_file and instrumental_audio_file.filename.split(".")[
            -1
        ] not in ["mp3"]:
            return {"is_valid": False, "message": "Invalid MP3 file format"}

        if upright_audio_file and upright_audio_file.filename.split(".")[-1] not in [
            "mp3"
        ]:
            return {"is_valid": False, "message": "Invalid MP3 file format"}

        if reverse_audio_file and reverse_audio_file.filename.split(".")[-1] not in [
            "mp3"
        ]:
            return {"is_valid": False, "message": "Invalid MP3 file format"}

        if hires_audio_file and hires_audio_file.filename.split(".")[-1] not in [
            "wav",
            "mp3",
        ]:
            return {"is_valid": False, "message": "Invalid WAV file format"}

        if cover_image_file and cover_image_file.filename.split(".")[-1] not in [
            "jpg",
            "jpeg",
            "png",
        ]:
            return {"is_valid": False, "message": "Invalid cover file format"}

        return {"is_valid": True, "message": "Valid file format"}

    # update a track
    async def update_track(
        self,
        track_id: UUID4,
        track_data: UpdateTrack,
        cover_image_file: Optional[UploadFile],
        instrumental_audio_file: Optional[UploadFile],
        upright_audio_file: Optional[UploadFile],
        reverse_audio_file: Optional[UploadFile],
        hires_audio_file: Optional[UploadFile],
    ) -> Track:

        try:

            track = await self.get_track_by_id(track_id)

            s3_client = S3FileClient()
            folder_name = f"tracks/{track.name}"

            if instrumental_audio_file:
                instrumental_audio_file_content = await instrumental_audio_file.read()
                # Upload the mp3 file
                mp3_url = s3_client.upload_file_if_not_exists(
                    folder_name=folder_name,
                    file_name=instrumental_audio_file.filename,
                    file_content=instrumental_audio_file_content,
                    content_type=instrumental_audio_file.content_type,
                )

                # extract the upright mp3 audio metadata
                audio_analyzer = AudioAnalyzerService()
                track_technical_data = await audio_analyzer.analyze(
                    file_content=instrumental_audio_file_content,
                    file_name=instrumental_audio_file.filename,
                )
                track.track_technical_data = json.dumps(track_technical_data)
                track.instrumental_audio_url = mp3_url

            if hires_audio_file:
                hires_audio_file_content = await hires_audio_file.read()

                hi_res_url = s3_client.upload_file_if_not_exists(
                    folder_name=folder_name,
                    file_name=hires_audio_file.filename,
                    file_content=hires_audio_file_content,
                    content_type=hires_audio_file.content_type,
                )
                track.hires_audio_url = hi_res_url

            if cover_image_file:
                cover_image_file_content = await cover_image_file.read()

                cover_image_url = s3_client.upload_file_if_not_exists(
                    folder_name=folder_name,
                    file_name=cover_image_file.filename,
                    file_content=cover_image_file_content,
                    content_type=cover_image_file.content_type,
                )
                track.cover_image = cover_image_url

                # create the thumbnail version of the image
                resized_image_data = await resize_image(
                    file_content=cover_image_file_content,
                    file_name=cover_image_file.filename,
                    file_content_type=cover_image_file.content_type,
                    height=settings.THUMBNAIL_HEIGHT,
                    width=settings.THUMBNAIL_WIDTH,
                )

                # upload the thumbnail to s3 bucket and get the url
                thumbnail_uploaded_url = s3_client.upload_file_if_not_exists(
                    folder_name=folder_name,
                    file_name=resized_image_data["file_name"],
                    file_content=resized_image_data["image_content"],
                    content_type=resized_image_data["file_content_type"],
                )
                track.thumbnail_image = thumbnail_uploaded_url

            if upright_audio_file:
                upright_audio_file_content = await upright_audio_file.read()

                upright_audio_url = s3_client.upload_file_if_not_exists(
                    folder_name=folder_name,
                    file_name=upright_audio_file.filename,
                    file_content=upright_audio_file_content,
                    content_type=upright_audio_file.content_type,
                )
                track.upright_audio_url = upright_audio_url

            if reverse_audio_file:
                reverse_audio_file_content = await reverse_audio_file.read()

                reverse_audio_url = s3_client.upload_file_if_not_exists(
                    folder_name=folder_name,
                    file_name=reverse_audio_file.filename,
                    file_content=reverse_audio_file_content,
                    content_type=reverse_audio_file.content_type,
                )
                track.reverse_audio_url = reverse_audio_url

            # Step 1: Explicitly update the updated_at field
            track_data.updated_at = datetime.utcnow()
            # Step 2: Update the fields with new values
            for field, value in track_data.dict().items():
                if (
                    value is not None
                ):  # Only update if the field was provided in the request
                    setattr(track, field, value)

                # Step 3: Commit the changes
                self.session.add(track)
                await self.session.commit()

            return track

        except Exception as e:
            raise e

    # delete a track by id
    async def delete_track(self, id: UUID4) -> bool:
        track_record = await self.session.execute(select(Track).where(Track.id == id))
        track: Track = track_record.scalar_one_or_none()

        if not track:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Track not found"
            )

        # delete 3 files from s3 bucket
        s3_client = S3FileClient()

        if track.instrumental_audio_url:
            instrumental_audio_path = (
                f'tracks/{track.name}/{track.instrumental_audio_url.split("/")[-1]}'
            )
            s3_client.delete_file(instrumental_audio_path)

        if track.upright_audio_url:
            upright_audio_path = (
                f'tracks/{track.name}/{track.upright_audio_url.split("/")[-1]}'
            )
            s3_client.delete_file(upright_audio_path)

        if track.hires_audio_url:
            hires_audio_path = (
                f'tracks/{track.name}/{track.hires_audio_url.split("/")[-1]}'
            )
            s3_client.delete_file(hires_audio_path)

        if track.cover_image:
            cover_image_path = f'tracks/{track.name}/{track.cover_image.split("/")[-1]}'
            s3_client.delete_file(cover_image_path)

        if track.thumbnail_image:
            cover_image_thumbnail_path = (
                f'tracks/{track.name}/{track.thumbnail_image.split("/")[-1]}'
            )
            s3_client.delete_file(cover_image_thumbnail_path)

        await self.session.delete(track)
        await self.session.commit()

        return True

    # delete all tracks by collection id
    async def delete_all_tracks_by_collection_id(self, collection_id: UUID4) -> bool:
        track_records = await self.session.execute(
            select(Track).where(Track.collection_id == collection_id)
        )
        tracks = track_records.scalars().all()

        if not tracks:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Track not found"
            )

        for track in tracks:
            await self.session.delete(track)

        await self.session.commit()

        return True

    async def generate_random_track_list(self, count: int) -> List[dict]:
        track_records = await self.session.execute(
            select(Track, Collection)
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

    # create a tracks
    async def bulk_create_tracks(
        track_list: List[Tuple],
        task_id: str,
        cache: dict,
        collection_id: UUID4,
        user_id: UUID4 | None = None,
        session: AsyncSession = Depends(db_session),
    ):

        try:

            total = len(track_list)
            task_id_str = str(task_id)
            cache[task_id_str] = {
                "status": "in progress",
                "progress": {"current": 0, "total": total},
            }

            s3_client = S3FileClient()

            for i, track_data in enumerate(track_list):
                (
                    mp3_file_content,
                    hi_res_file_content,
                    cover_image_content,
                    track_description,
                    track_short_description,
                    track_name,
                    mp3_file_name,
                    hi_res_file_name,
                    cover_image_name,
                    mp3_file_content_type,
                    hi_res_file_content_type,
                    cover_image_content_type,
                ) = track_data

                folder_name = f"tracks/{track_name}"
                # Upload the mp3 file
                mp3_url = s3_client.upload_file_if_not_exists(
                    folder_name=folder_name,
                    file_name=mp3_file_name,
                    file_content=mp3_file_content,
                    content_type=mp3_file_content_type,
                )

                # upload file to pinata
                ipfs_mp3_url = None

                # Upload hi_res file
                hi_res_url = s3_client.upload_file_if_not_exists(
                    folder_name=folder_name,
                    file_name=hi_res_file_name,
                    file_content=hi_res_file_content,
                    content_type=hi_res_file_content_type,
                )

                # upload file to pinata
                ipfs_hi_res_url = None

                # Upload hi_res file
                cover_image_url = s3_client.upload_file_if_not_exists(
                    folder_name=folder_name,
                    file_name=cover_image_name,
                    file_content=cover_image_content,
                    content_type=cover_image_content_type,
                )

                # upload file to pinata
                ipfs_cover_image = None

                # create the thumbnail version of the image
                resized_image_data = await resize_image(
                    file_content=cover_image_content,
                    file_name=cover_image_name,
                    file_content_type=cover_image_content_type,
                    height=settings.THUMBNAIL_HEIGHT,
                    width=settings.THUMBNAIL_WIDTH,
                )

                # upload the thumbnail to s3 bucket and get the url
                thumbnail_uploaded_url = s3_client.upload_file_if_not_exists(
                    folder_name=folder_name,
                    file_name=resized_image_data["file_name"],
                    file_content=resized_image_data["image_content"],
                    content_type=resized_image_data["file_content_type"],
                )

                # upload cover image thumbnail to pinata
                ipfs_thumbnail_image = None

                # Create track record
                track_record = Track(
                    collection_id=collection_id,
                    user_id=user_id,
                    name=track_name,
                    description=track_description,
                    short_description=track_short_description,
                    mp3_url=mp3_url,
                    hi_res_url=hi_res_url,
                    cover_image=cover_image_url,
                    thumbnail_image=thumbnail_uploaded_url,
                    ipfs_cover_image=ipfs_cover_image,
                    ipfs_thumbnail_image=ipfs_thumbnail_image,
                    ipfs_mp3_url=ipfs_mp3_url,
                    ipfs_hi_res_url=ipfs_hi_res_url,
                )
                session.add(track_record)
                await session.commit()
                cache[task_id]["progress"]["current"] = i + 1
            cache[task_id]["status"] = "done"
        except Exception as e:
            raise e

    async def search_tracks(self, query: str):
        search_query = f"%{query}%"  # Format the query for a LIKE search
        result = await self.session.execute(
            select(Track, Collection)
            .where(
                or_(
                    Track.name.ilike(search_query),
                    Track.description.ilike(search_query),
                    Track.short_description.ilike(search_query),
                )
            )
            .where(Track.is_private != True)
            .join(Collection, Track.collection_id == Collection.id)
        )
        results = result.all()
        tracks_with_collections = [
            {"track": track, "collection": collection} for track, collection in results
        ]

        return tracks_with_collections

    async def get_track_data_from_ids(self, track_ids: List[str]) -> dict:
        track_ids = [uuid_pkg.UUID(id) for id in track_ids]

        track_records = await self.session.execute(
            select(Track, Collection)
            .where(Track.id.in_(track_ids))
            .where(Track.is_hidden != True)
            .where(Track.is_private != True)
            .join(Collection, Track.collection_id == Collection.id)
        )
        results = track_records.all()

        if len(results) > 10:
            results = results[:10]

        # Create a list of dictionaries with track and collection details
        tracks_with_collections = [
            {"track": track, "collection": collection} for track, collection in results
        ]
        return tracks_with_collections
