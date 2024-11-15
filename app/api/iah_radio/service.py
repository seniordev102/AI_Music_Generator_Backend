import os
import tempfile
import uuid
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import requests
from fastapi import Depends
from openai import OpenAI
from sqlalchemy import String, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.http_response_model import PageMeta
from app.config import settings
from app.database import db_session
from app.logger.logger import logger
from app.models import Category, Collection, Track
from app.schemas import GetIahRadioTracks


class IAHRadioService:
    def __init__(
        self,
        session: AsyncSession = Depends(db_session),
    ) -> None:
        self.session = session

    async def get_all_tracks_for_iah_radio(
        self,
        page: int,
        page_size: int,
        is_lyrical: Optional[bool],
        is_legacy: Optional[bool],
    ) -> Tuple[List[Dict[str, Any]], PageMeta]:
        tracks_to_skip = (page - 1) * page_size

        # Base query with JOIN
        query = (
            select(Track, Collection)
            .join(Collection, Track.collection_id == Collection.id)
            .where(Track.is_private != True)
        )

        # Initialize an empty list for collection IDs
        combined_collection_ids = []

        # Add conditions dynamically
        if is_lyrical is not None or is_legacy is not None:
            if is_lyrical:
                # Get the collection ID list where Collection.is_iah_radio is True
                lyrical_collection_ids = await self.session.execute(
                    select(Collection.id).where(Collection.is_iah_radio == True)
                )
                combined_collection_ids.extend(lyrical_collection_ids.scalars().all())

            if is_legacy:
                # Special curated category ID
                category_id = "b9f79171-191c-49c4-9d53-717c24316d21"
                legacy_collection_ids = await self.session.execute(
                    select(Category.collection_ids).where(Category.id == category_id)
                )
                legacy_collection_ids = legacy_collection_ids.scalars().all()
                if len(legacy_collection_ids) == 1 and isinstance(
                    legacy_collection_ids[0], str
                ):
                    legacy_collection_ids = legacy_collection_ids[0].split(",")

                # Parse legacy collection IDs to UUID objects
                combined_collection_ids.extend(
                    UUID(id.strip()) for id in legacy_collection_ids
                )

            if combined_collection_ids:
                # Filter by combined collection IDs
                query = query.where(Collection.id.in_(combined_collection_ids))

                # Apply `is_lyrical` condition
                if is_lyrical and not is_legacy:
                    query = query.where(Track.is_lyrical == True)
                elif is_legacy and not is_lyrical:
                    query = query.where(Track.is_lyrical == False)

            else:
                # If both are True or combined IDs are empty, return empty
                return [], PageMeta(
                    page=page, page_size=page_size, total_pages=0, total_items=0
                )

        else:
            # If both `is_lyrical` and `is_legacy` are False, return empty
            return [], PageMeta(
                page=page, page_size=page_size, total_pages=0, total_items=0
            )

        # Get total number of items
        total_items_query = select(func.count()).select_from(query.subquery())
        total_items = (await self.session.execute(total_items_query)).scalar()

        # Calculate total pages
        total_pages = -(-total_items // page_size)

        # Apply pagination
        query = query.offset(tracks_to_skip).limit(page_size).order_by(func.random())

        # Fetch the items
        result = await self.session.execute(query)
        tracks_with_collections = result.fetchall()

        # Convert to list of structured dictionaries
        structured_data = []
        for track, collection in tracks_with_collections:
            track_dict = track.__dict__
            collection_dict = collection.__dict__

            # Remove SQLAlchemy internal state
            track_dict.pop("_sa_instance_state", None)
            collection_dict.pop("_sa_instance_state", None)

            structured_data.append({"track": track_dict, "collection": collection_dict})

        # Return the result with pagination metadata
        return structured_data, PageMeta(
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            total_items=total_items,
        )

    async def get_all_tracks_for_iah_radio_based_on_collections(
        self,
        page: int,
        page_size: int,
        filter_data: GetIahRadioTracks,
        salt: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], PageMeta, str]:
        # Generate a new salt if none provided
        if salt is None or salt == "":
            salt = str(uuid.uuid4())

        tracks_to_skip = (page - 1) * page_size
        collection_ids_list = []

        if filter_data.is_legacy:
            WHEEL_OF_FORTUNE_COLLECTION_ID = "cd708d0a-42ae-4336-9063-093f5fef4d6d"
            # Get all legacy collections if legacy mode is on
            legacy_collection_record = await self.session.execute(
                select(Collection.id)
                .where(Collection.is_private != True)
                .where(
                    or_(
                        Collection.is_iah_radio != True,
                        Collection.is_iah_radio.is_(None),
                    )
                )
                .where(Collection.id != WHEEL_OF_FORTUNE_COLLECTION_ID)
            )
            legacy_collections_ids = legacy_collection_record.scalars().all()
            legacy_collection_strings = [str(uuid) for uuid in legacy_collections_ids]
            collection_ids_list = legacy_collection_strings

            if filter_data.selected_collections:
                collection_ids_list.extend(filter_data.selected_collections)

            # Remove duplicates while preserving order
            collection_ids_list = list(dict.fromkeys(collection_ids_list))
        else:
            collection_ids_list = filter_data.selected_collections

        # Base query joining tracks and collections
        query = (
            select(Track, Collection)
            .join(Collection, Track.collection_id == Collection.id)
            .where(
                Track.is_private != True,
                Collection.id.in_([UUID(id) for id in collection_ids_list]),
            )
        )

        # Order by hash of track ID with salt for consistent randomization
        query = query.order_by(func.md5(func.cast(Track.id, String) + salt), Track.id)

        # Get total count for pagination
        total_items_query = select(func.count()).select_from(query.subquery())
        total_items = (await self.session.execute(total_items_query)).scalar()

        # Calculate total pages (ceiling division)
        total_pages = -(-total_items // page_size)

        # If no items found, return empty result
        if total_items == 0:
            return (
                [],
                PageMeta(page=page, page_size=page_size, total_pages=0, total_items=0),
                salt,
            )

        # Apply pagination
        query = query.offset(tracks_to_skip).limit(page_size)

        # Execute query and fetch results
        result = await self.session.execute(query)
        tracks_with_collections = result.fetchall()

        # Structure the response data
        structured_data = []
        for track, collection in tracks_with_collections:
            track_dict = track.__dict__.copy()
            collection_dict = collection.__dict__.copy()

            # Remove SQLAlchemy internal state
            track_dict.pop("_sa_instance_state", None)
            collection_dict.pop("_sa_instance_state", None)

            structured_data.append({"track": track_dict, "collection": collection_dict})

        # Note: Removed random.shuffle and structured_data.sort as ordering is now handled by the query

        return (
            structured_data,
            PageMeta(
                page=page,
                page_size=page_size,
                total_pages=total_pages,
                total_items=total_items,
            ),
            salt,
        )

    async def generate_lyrics_for_iah_radio_tracks(self):

        query = (
            select(Track)
            .where(Track.is_lyrical == True)
            .where(Track.srt_lyrics == None)
        )
        track_records = await self.session.execute(query)
        tracks = track_records.scalars().all()

        for track in tracks:
            str_output = self._transcribe_audio_from_url(track.instrumental_audio_url)
            track.srt_lyrics = str_output
            await self.session.commit()

        return None

    async def generate_missing_lyrics(self):
        query = select(Track).where(Track.srt_lyrics == None).limit(5)
        track_records = await self.session.execute(query)
        tracks = track_records.scalars().all()

        for track in tracks:
            str_output = self._transcribe_audio_from_url(track.upright_audio_url)
            track.srt_lyrics = str_output
            await self.session.commit()

        return len(tracks)

    async def get_iah_radio_collections(self):

        query = (
            select(Collection)
            .where(Collection.is_iah_radio == True)
            .where(Collection.is_private != True)
            .order_by(Collection.order_seq)
        )
        iah_radio_collection_records = await self.session.execute(query)
        collections = iah_radio_collection_records.scalars().all()

        return collections

    def _transcribe_audio_from_url(self, audio_url) -> Tuple[str, str]:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        try:
            # Download the audio file
            logger.debug(f"Downloading audio file... {audio_url}")
            response = requests.get(audio_url, stream=True)
            response.raise_for_status()

            # Create a temporary file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                # Write the content to the temporary file
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        temp_file.write(chunk)
                temp_file.flush()

                # Reopen the file in binary read mode
                with open(temp_file.name, "rb") as audio_file:
                    # Transcribe the audio
                    logger.debug(
                        "Transcribing audio file. This may take a few minutes..."
                    )
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        response_format="srt",
                    )

            # Clean up the temporary file
            os.unlink(temp_file.name)

            return transcript

        except requests.exceptions.RequestException as e:
            raise Exception(f"Error downloading audio file: {e}")
        except Exception as e:
            raise Exception(f"Error during transcription: {e}")
