from typing import List, Union

from fastapi import Depends, HTTPException, status
from pydantic import UUID4
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import db_session
from app.models import Collection, FavoriteIAHResponse, FavoriteTrack, Track, User
from app.schemas import CreateFavoritePromptResponse, CreateFavoriteTrack


class FavoriteService:
    def __init__(
        self,
        session: AsyncSession = Depends(db_session),
    ) -> None:
        self.session = session

    async def get_all_user_favorite_tracks(
        self, email: str
    ) -> List[dict[str, Union[Track, Collection]]]:

        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            return []

        user_favorite_tracks_records = await self.session.execute(
            select(FavoriteTrack).where(FavoriteTrack.user_id == user.id)
        )
        user_favorite_tracks = user_favorite_tracks_records.scalars().all()

        # filter out track ids
        track_ids = [track.track_id for track in user_favorite_tracks]
        track_records = await self.session.execute(
            select(Track, Collection).where(Track.id.in_(track_ids))
            # Manual join condition
            .join(Collection, Track.collection_id == Collection.id)
        )
        results = track_records.all()

        # Create a list of dictionaries with track and collection details
        tracks_with_collections = [
            {"track": track, "collection": collection} for track, collection in results
        ]

        return tracks_with_collections

    async def get_is_track_favorite_by_user(self, email: str, track_id: UUID4) -> bool:

        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            return False

        favorite_track_record = await self.session.execute(
            select(FavoriteTrack)
            .where(FavoriteTrack.user_id == user.id)
            .where(FavoriteTrack.track_id == track_id)
        )
        favorite_track = favorite_track_record.scalar_one_or_none()

        if not favorite_track:
            return False
        else:
            return True

    async def get_all_user_favorite_iah_responses(
        self, user_id: UUID4
    ) -> List[FavoriteIAHResponse]:
        user_favorite_iah_response_records = await self.session.execute(
            select(FavoriteIAHResponse).where(FavoriteIAHResponse.user_id == user_id)
        )
        user_favorite_iah_responses = user_favorite_iah_response_records.scalars().all()
        return user_favorite_iah_responses

    async def create_favorite_track(
        self, data: CreateFavoriteTrack, user_email: str
    ) -> FavoriteTrack:

        user_record = await self.session.execute(
            select(User).where(User.email == user_email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Check if the track is already in the user's favorite list
        favorite_track_record = await self.session.execute(
            select(FavoriteTrack)
            .where(FavoriteTrack.user_id == user.id)
            .where(FavoriteTrack.track_id == data.track_id)
        )

        favorite_track = favorite_track_record.scalar_one_or_none()

        if favorite_track:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Track already in favorite list",
            )

        favorite_track = FavoriteTrack(
            user_id=user.id, track_id=data.track_id, collection_id=data.collection_id
        )
        self.session.add(favorite_track)
        await self.session.commit()
        return favorite_track

    async def create_favorite_iah_response(
        self, data: CreateFavoritePromptResponse, user_email: str
    ) -> FavoriteIAHResponse:

        user_record = await self.session.execute(
            select(User).where(User.email == user_email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        favorite_iah_response = FavoriteIAHResponse(
            user_id=user.id,
            message_id=data.message_id,
            session_id=data.session_id,
            response=data.response,
        )
        self.session.add(favorite_iah_response)
        await self.session.commit()
        return favorite_iah_response

    async def delete_favorite_track(self, email: str, track_id: UUID4) -> bool:

        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        favorite_track_record = await self.session.execute(
            select(FavoriteTrack)
            .where(FavoriteTrack.user_id == user.id)
            .where(FavoriteTrack.track_id == track_id)
        )
        favorite_track = favorite_track_record.scalar_one_or_none()

        if not favorite_track:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Favorite track not found"
            )

        await self.session.delete(favorite_track)
        await self.session.commit()
        return True

    async def delete_favorite_iah_response(
        self, user_email: str, message_id: UUID4
    ) -> bool:

        user_record = await self.session.execute(
            select(User).where(User.email == user_email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        favorite_iah_response_record = await self.session.execute(
            select(FavoriteIAHResponse)
            .where(FavoriteIAHResponse.user_id == user.id)
            .where(FavoriteIAHResponse.message_id == message_id)
        )
        favorite_iah_response = favorite_iah_response_record.scalar_one_or_none()

        if not favorite_iah_response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Favorite IAH response not found",
            )

        await self.session.delete(favorite_iah_response)
        await self.session.commit()
        return True
