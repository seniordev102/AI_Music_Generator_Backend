import uuid as uuid_pkg
from typing import List, Union

from fastapi import Depends, HTTPException, status
from pydantic import UUID4
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import db_session
from app.models import Collection, Playlist, Track, User
from app.schemas import (
    AddTrackToPlaylist,
    CopyPlaylist,
    CreatePlaylist,
    DeleteTrackFromPlaylist,
    UpdatePlaylist,
    UpdatePlaylistTracks,
)


class PlaylistService:
    def __init__(
        self,
        session: AsyncSession = Depends(db_session),
    ) -> None:
        self.session = session

    async def get_all_playlist_by_user(self, email: str):
        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            return []

        user_playlists_records = await self.session.execute(
            select(Playlist).where(Playlist.user_id == user.id)
        )
        user_playlists: List[Playlist] = user_playlists_records.scalars().all()

        if not user_playlists:
            return []
        playlist_data = []
        for user_playlist in user_playlists:
            track_ids = user_playlist.track_ids.split(",")

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

    async def get_public_playlist_by_id(self, playlist_id: UUID4):
        playlist_record = await self.session.execute(
            select(Playlist).where(Playlist.id == playlist_id)
        )
        playlist: Playlist = playlist_record.scalar_one_or_none()

        if playlist.is_public == False:
            raise HTTPException(
                detail="Access Denied: The requested playlist is private and only accessible to its owner.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not playlist:
            return None

        track_ids = playlist.track_ids.split(",")  # e.g. ["uuid1", "uuid2", ...]

        tracks_with_collections = []
        # If the playlist has valid track_ids
        if track_ids not in ([], [""]):
            # Fetch all tracks (and their collections) in *any* order
            track_records = await self.session.execute(
                select(Track, Collection)
                .where(Track.id.in_(track_ids))
                .join(Collection, Track.collection_id == Collection.id)
            )
            results = track_records.all()  # List of (Track, Collection) tuples

            # Build a lookup dict: track_id → (Track, Collection)
            track_dict = {
                str(track.id): (track, collection) for track, collection in results
            }

            # Reconstruct the list in the same order as track_ids
            for tid in track_ids:
                pair = track_dict.get(tid)
                if pair:
                    track, collection = pair
                    tracks_with_collections.append(
                        {"track": track, "collection": collection}
                    )

        # Get user info
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

    async def get_user_playlist_by_id(self, user_email: str, playlist_id: UUID4):

        user_record = await self.session.execute(
            select(User).where(User.email == user_email)
        )
        user: User = user_record.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                detail="User not found", status_code=status.HTTP_404_NOT_FOUND
            )

        playlist_record = await self.session.execute(
            select(Playlist).where(Playlist.id == playlist_id)
        )
        playlist: Playlist = playlist_record.scalar_one_or_none()

        if playlist is None:
            raise HTTPException(
                detail="Playlist not found", status_code=status.HTTP_404_NOT_FOUND
            )

        if playlist.user_id != user.id:
            raise HTTPException(
                detail="Access denied: You don't have permission to view this playlist",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        track_ids = playlist.track_ids.split(",")

        tracks_with_collections = []
        # If the playlist has valid track_ids
        if track_ids not in ([], [""]):
            # Fetch all tracks (and their collections) in *any* order
            track_records = await self.session.execute(
                select(Track, Collection)
                .where(Track.id.in_(track_ids))
                .join(Collection, Track.collection_id == Collection.id)
            )
            results = track_records.all()  # List of (Track, Collection) tuples

            # Build a lookup dict: track_id → (Track, Collection)
            track_dict = {
                str(track.id): (track, collection) for track, collection in results
            }

            # Reconstruct the list in the same order as track_ids
            for tid in track_ids:
                pair = track_dict.get(tid)
                if pair:
                    track, collection = pair
                    tracks_with_collections.append(
                        {"track": track, "collection": collection}
                    )

        # Get user info
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

    async def get_user_playlist_count(self, email: str):
        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            return 0

        user_playlists_count = await self.session.execute(
            select(func.count())
            .select_from(Playlist)
            .where(Playlist.user_id == user.id)
        )
        playlist_count = user_playlists_count.scalar()

        return playlist_count

    async def create_playlist(
        self, email: str, playlist_data: CreatePlaylist
    ) -> Playlist:

        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # convert track_ids to string
        playlist_data.track_ids = ",".join(playlist_data.track_ids)
        playlist = Playlist(
            user_id=user.id,
            name=playlist_data.name,
            description=playlist_data.description,
            short_description=playlist_data.short_description,
            cover_image=playlist_data.cover_image,
            track_ids=playlist_data.track_ids,
        )

        self.session.add(playlist)
        await self.session.commit()
        return playlist

    async def copy_playlist(
        self, user_email: str, playlist_id: uuid_pkg.UUID, playlist_data: CopyPlaylist
    ) -> Playlist:

        user_record = await self.session.execute(
            select(User).where(User.email == user_email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # get the playlist by playlist id
        query = select(Playlist).where(Playlist.id == playlist_id)

        record = await self.session.execute(query)
        playlist = record.scalar_one_or_none()

        if playlist is None:
            raise HTTPException(
                detail="Playlist not found", status_code=status.HTTP_404_NOT_FOUND
            )

        if playlist.is_public == False:
            raise HTTPException(
                detail="Unable to copy: Playlist access is set to private",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # check user id and playlist user id equal
        if user.id == playlist.user_id:
            raise HTTPException(
                detail="Unable to copy: You cannot duplicate your own playlist",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        new_playlist_name = None
        new_playlist_description = None
        new_playlist_cover_image = None

        if playlist_data.name is None:
            new_playlist_name = playlist.name
        else:
            new_playlist_name = playlist_data.name

        if playlist_data.description is None:
            new_playlist_description = playlist.description
        else:
            new_playlist_description = playlist_data.description

        if playlist_data.cover_image is None:
            new_playlist_cover_image = playlist.cover_image
        else:
            new_playlist_cover_image = playlist_data.cover_image

        # if everything is fine then let's create a new playlist
        new_playlist = Playlist(
            user_id=user.id,
            name=new_playlist_name,
            description=new_playlist_description,
            track_ids=playlist.track_ids,
            cover_image=new_playlist_cover_image,
        )

        self.session.add(new_playlist)
        await self.session.commit()
        return new_playlist

    async def update_playlist(
        self, email: str, playlist_data: UpdatePlaylist, playlist_id: UUID4
    ) -> Playlist:

        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        playlist_record = await self.session.execute(
            select(Playlist).where(Playlist.id == playlist_id)
        )
        playlist: Playlist = playlist_record.scalar_one_or_none()

        if not playlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found"
            )

        if playlist.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to update this playlist",
            )

        # Convert playlist_data to dict and remove None values
        update_data = playlist_data.dict(exclude_unset=True)

        # Handle track_ids separately if present
        if "track_ids" in update_data:
            update_data["track_ids"] = ",".join(update_data["track_ids"])

        # Update playlist with non-null values
        for key, value in update_data.items():
            setattr(playlist, key, value)

        self.session.add(playlist)
        await self.session.commit()
        return playlist

    async def update_playlist_tracks(
        self, email: str, playlist_tracks: UpdatePlaylistTracks, playlist_id: UUID4
    ) -> Playlist:

        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        playlist_record = await self.session.execute(
            select(Playlist).where(Playlist.id == playlist_id)
        )
        playlist: Playlist = playlist_record.scalar_one_or_none()

        if not playlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found"
            )

        if playlist.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to update this playlist",
            )

        # convert track_ids to string
        playlist_tracks.track_ids = ",".join(playlist_tracks.track_ids)

        # update the playlist tracks
        playlist.track_ids = playlist_tracks.track_ids

        self.session.add(playlist)
        await self.session.commit()
        return playlist

    async def delete_track_from_playlist(
        self, email: str, delete_playlist_data: DeleteTrackFromPlaylist
    ) -> Playlist:

        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        playlist_record = await self.session.execute(
            select(Playlist).where(Playlist.id == delete_playlist_data.playlist_id)
        )
        playlist: Playlist = playlist_record.scalar_one_or_none()

        if not playlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found"
            )

        if playlist.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to update this playlist",
            )

        track_ids = playlist.track_ids.split(",")
        track_ids.remove(str(delete_playlist_data.track_id))
        playlist.track_ids = ",".join(track_ids)

        self.session.add(playlist)
        await self.session.commit()
        return playlist

    async def delete_playlist(
        self, email: str, playlist_id: UUID4
    ) -> Union[Playlist, None]:
        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        playlist_record = await self.session.execute(
            select(Playlist).where(Playlist.id == playlist_id)
        )
        playlist: Playlist = playlist_record.scalar_one_or_none()

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

    async def add_new_track_to_playlist(
        self, email: str, add_track_data: AddTrackToPlaylist
    ) -> Playlist:

        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        if add_track_data.playlist_id is None:
            # create a playlist and add the track
            # get current user playlist count
            playlist_count = await self.get_user_playlist_count(email)
            playlist_name = f"My Playlist #{playlist_count + 1}"
            playlist_data = CreatePlaylist(
                name=playlist_name,
                description=None,
                short_description=None,
                cover_image=None,
                track_ids=[str(add_track_data.track_id)],
            )

            return await self.create_playlist(email, playlist_data)
        else:
            playlist_record = await self.session.execute(
                select(Playlist).where(Playlist.id == add_track_data.playlist_id)
            )
            playlist: Playlist = playlist_record.scalar_one_or_none()

            if not playlist:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found"
                )

            if playlist.user_id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not authorized to update this playlist",
                )

            track_ids = playlist.track_ids.split(",")
            track_ids.append(str(add_track_data.track_id))
            playlist.track_ids = ",".join(track_ids)

            self.session.add(playlist)
            await self.session.commit()
            return playlist
