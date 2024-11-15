from typing import List, Union

from fastapi import Depends, HTTPException, status
from pydantic import UUID4
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import db_session
from app.models import Collection, PlaylistType, SonicPlaylist, Track, User
from app.schemas import CreateSonicPlaylist, UpdateSonicPlaylist


class SonicPlaylistService:
    def __init__(
        self,
        session: AsyncSession = Depends(db_session),
    ) -> None:
        self.session = session

    async def create_sonic_playlist(
        self, email: str, playlist_data: CreateSonicPlaylist
    ) -> SonicPlaylist:

        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # convert track_ids to string
        track_ids_str = ",".join([str(u) for u in playlist_data.selected_track_ids])
        sonic_playlist = SonicPlaylist(
            user_id=str(user.id),
            name=playlist_data.name,
            description=playlist_data.description,
            selected_track_ids=track_ids_str,
            selected_category=str(playlist_data.selected_category),
            selected_collection=str(playlist_data.selected_collection),
            cover_image=playlist_data.cover_image,
            cover_image_thumbnail=playlist_data.cover_image_thumbnail,
            square_image=playlist_data.square_image,
            square_thumbnail_image=playlist_data.square_image_thumbnail,
            cover_image_prompt=playlist_data.cover_image_prompt,
            square_image_prompt=playlist_data.square_image_prompt,
            playlist_type=playlist_data.playlist_type,
            is_playlist=playlist_data.is_playlist,
        )

        self.session.add(sonic_playlist)
        await self.session.commit()
        return sonic_playlist

    async def update_sonic_playlist(
        self, email: str, playlist_id: UUID4, playlist_data: UpdateSonicPlaylist
    ) -> SonicPlaylist:

        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        playlist_record = await self.session.execute(
            select(SonicPlaylist)
            .where(SonicPlaylist.id == playlist_id)
            .where(SonicPlaylist.playlist_type == PlaylistType.SONIC_SUPPLEMENT)
        )

        playlist: SonicPlaylist = playlist_record.scalar_one_or_none()

        if not playlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found"
            )

        FIELD_MAPPING = {
            "name": "name",
            "description": "description",
            "selected_category": "selected_category",
            "selected_collection": "selected_collection",
            "cover_image": "cover_image",
            "cover_image_thumbnail": "cover_image_thumbnail",
            "square_image": "square_image",
            "square_image_thumbnail": "square_thumbnail_image",
            "selected_track_ids": "selected_track_ids",
            "playlist_type": "playlist_type",
            "social_media_title": "social_media_title",
            "social_media_description": "social_media_description",
            "is_social_media": "is_social_media",
            "is_playlist": "is_playlist",
        }

        if playlist_data.selected_category:
            playlist_data.selected_category = str(playlist_data.selected_category)

        if playlist_data.selected_collection:
            playlist_data.selected_collection = str(playlist_data.selected_collection)

        # Convert list of UUIDs to comma-separated string if selected_track_ids is provided
        if playlist_data.selected_track_ids is not None:
            track_ids_str = ",".join([str(u) for u in playlist_data.selected_track_ids])
            setattr(playlist, FIELD_MAPPING["selected_track_ids"], track_ids_str)

        # Update other fields if available in the payload
        for schema_field, model_field in FIELD_MAPPING.items():
            if (
                schema_field != "selected_track_ids"
            ):  # Skip selected_track_ids, already handled
                value = getattr(playlist_data, schema_field)
                if value is not None:
                    setattr(playlist, model_field, value)

        self.session.add(playlist)
        await self.session.commit()

        return playlist

    async def get_all_playlist_by_user(self, email: str):
        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            return []

        user_playlists_records = await self.session.execute(
            select(SonicPlaylist)
            .where(SonicPlaylist.user_id == user.id)
            .where(SonicPlaylist.is_playlist == True)
            .where(SonicPlaylist.is_pinned == False)
            .order_by(SonicPlaylist.created_at.desc())
        )
        user_playlists: List[SonicPlaylist] = user_playlists_records.scalars().all()

        if not user_playlists:
            return []
        playlist_data = []
        for user_playlist in user_playlists:
            track_ids = user_playlist.selected_track_ids.split(",")

            tracks_with_collections = []
            if track_ids not in [[], [""]]:
                track_records = await self.session.execute(
                    select(Track, Collection).where(Track.id.in_(track_ids))
                    # Manual join condition
                    .join(Collection, Track.collection_id == Collection.id)
                )
                results = track_records.all()

                # Create a list of dictionaries with track and collection details
                tracks_with_collections = [
                    {"track": track, "collection": collection}
                    for track, collection in results
                ]
                playlist_data.append(
                    {
                        "playlist": user_playlist,
                        "tracks_details": tracks_with_collections,
                    }
                )
            else:
                playlist_data.append({"playlist": user_playlist, "tracks_details": []})

        return playlist_data

    async def get_sonic_playlist_by_id(self, playlist_id: UUID4):
        playlist_record = await self.session.execute(
            select(SonicPlaylist).where(SonicPlaylist.id == playlist_id)
        )

        playlist: SonicPlaylist = playlist_record.scalar_one_or_none()

        if not playlist:
            return None

        track_ids = playlist.selected_track_ids.split(",")

        tracks_with_collections = []
        if track_ids not in [[], [""]]:
            # Fetch all tracks and collections in one query
            track_records = await self.session.execute(
                select(Track, Collection)
                .where(Track.id.in_(track_ids))
                .join(Collection, Track.collection_id == Collection.id)
            )
            results = track_records.all()

            # Create a dictionary mapping track IDs to their details
            track_dict = {
                str(track.id): {"track": track, "collection": collection}
                for track, collection in results
            }

            # Create the final list in the order of track_ids
            tracks_with_collections = [
                track_dict[track_id] for track_id in track_ids if track_id in track_dict
            ]

        # get user details
        user_record = await self.session.execute(
            select(User).where(User.id == playlist.user_id)
        )
        user: User = user_record.scalar_one_or_none()

        playlist_data = {
            "playlist": playlist,
            "tracks_details": tracks_with_collections,
            "user": user,
        }

        return playlist_data

    async def get_user_sonic_playlist_count(self, email: str):
        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            return 0

        user_playlists_count = await self.session.execute(
            select(func.count())
            .select_from(SonicPlaylist)
            .where(SonicPlaylist.user_id == user.id)
        )
        playlist_count = user_playlists_count.scalar()

        return playlist_count

    async def delete_sonic_playlist(
        self, email: str, playlist_id: UUID4
    ) -> Union[SonicPlaylist, None]:
        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        playlist_record = await self.session.execute(
            select(SonicPlaylist).where(SonicPlaylist.id == playlist_id)
        )
        playlist: SonicPlaylist = playlist_record.scalar_one_or_none()

        if not playlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found"
            )

        if playlist.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to delete this playlist",
            )

        await self.session.delete(playlist)
        await self.session.commit()
        return playlist

    async def change_pinned_status_of_playlist(
        self, email: str, playlist_id: UUID4, pinned_status: bool
    ) -> Union[SonicPlaylist, None]:
        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        playlist_record = await self.session.execute(
            select(SonicPlaylist).where(SonicPlaylist.id == playlist_id)
        )
        playlist: SonicPlaylist = playlist_record.scalar_one_or_none()

        if not playlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found"
            )

        if playlist.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to delete this playlist",
            )

        query = text(
            """
            UPDATE sonic_playlists
            SET is_pinned = :is_pinned
            WHERE id = :id
            """
        )

        await self.session.execute(
            query,
            {
                "is_pinned": pinned_status,
                "id": playlist_id,
            },
        )
        await self.session.commit()

        # Refresh the playlist object to get the updated data
        await self.session.refresh(playlist)

        return playlist

    async def get_all_pinned_playlist_by_user(self, email: str):
        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            return []

        user_playlists_records = await self.session.execute(
            select(SonicPlaylist)
            .where(SonicPlaylist.user_id == user.id)
            .where(SonicPlaylist.is_playlist == True)
            .where(SonicPlaylist.is_pinned == True)
            .order_by(SonicPlaylist.created_at.desc())
        )
        user_playlists: List[SonicPlaylist] = user_playlists_records.scalars().all()

        if not user_playlists:
            return []
        playlist_data = []
        for user_playlist in user_playlists:
            track_ids = user_playlist.selected_track_ids.split(",")

            tracks_with_collections = []
            if track_ids not in [[], [""]]:
                track_records = await self.session.execute(
                    select(Track, Collection).where(Track.id.in_(track_ids))
                    # Manual join condition
                    .join(Collection, Track.collection_id == Collection.id)
                )
                results = track_records.all()

                # Create a list of dictionaries with track and collection details
                tracks_with_collections = [
                    {"track": track, "collection": collection}
                    for track, collection in results
                ]
                playlist_data.append(
                    {
                        "playlist": user_playlist,
                        "tracks_details": tracks_with_collections,
                    }
                )
            else:
                playlist_data.append({"playlist": user_playlist, "tracks_details": []})

        return playlist_data
