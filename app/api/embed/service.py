from fastapi import Depends
from pydantic import UUID4
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import db_session
from app.models import SonicPlaylist, User


class EmbedService:
    def __init__(self, session: AsyncSession = Depends(db_session)) -> None:
        self.session = session

    async def search_all_craft_my_sonic(self, query: str):
        search_query = f"%{query}%"
        sonic_playlist_records = await self.session.execute(
            select(SonicPlaylist, User)
            .join(User, SonicPlaylist.user_id == User.id)  # Add this line
            .where(
                or_(
                    SonicPlaylist.name.ilike(search_query),
                    SonicPlaylist.description.ilike(search_query),
                    SonicPlaylist.user_input_title.ilike(search_query),
                    SonicPlaylist.user_input_prompt.ilike(search_query),
                    SonicPlaylist.social_media_title.ilike(search_query),
                    SonicPlaylist.social_media_description.ilike(search_query),
                )
            )
        )
        results = sonic_playlist_records.all()
        playlist_with_users = [
            {"playlist": sonic_playlist, "user": user}
            for sonic_playlist, user in results
        ]

        return playlist_with_users
