import logging
import os
from typing import List

from fastapi import Depends
from langchain.prompts import load_prompt
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import db_session
from app.models import Track
from app.schemas import CraftMySonicTrackSummary, SelectedTrackList


class OracleSummarizeService:
    def __init__(self, session: AsyncSession = Depends(db_session)) -> None:
        self.session = session
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
        )
        self.logger = logging.getLogger(__name__)

    def _load_prompt_from_file(self, file_path: str):
        """
        Load a prompt from a specified file path.
        """
        script_path = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_path)
        target_file_path = os.path.join(script_dir, file_path)
        return load_prompt(target_file_path)

    async def _extract_details_from_db(self, track_details: SelectedTrackList) -> dict:
        """
        Extract details from the selected values of the sonic supplement request.
        """

        # Get all the track details
        track_records = await self.session.execute(
            select(Track).where(Track.id.in_(track_details.selected_tracks))
        )
        selected_tracks: List[Track] = track_records.scalars().all()

        # Create a mapping from track IDs to tracks
        track_dict = {track.id: track for track in selected_tracks}

        # Ensure the tracks are in the same order as the IDs in track_details.selected_tracks
        ordered_tracks = [
            track_dict[track_id]
            for track_id in track_details.selected_tracks
            if track_id in track_dict
        ]

        track_details_list = []
        for track in ordered_tracks:
            track_details_list.append(
                {
                    "name": track.name,
                    "description": track.description,
                    "short_description": track.short_description,
                    "frequency_meaning": track.frequency_meaning,
                }
            )

        return {
            "track_details": track_details_list,
        }

    async def generate_summary(self, track_details: SelectedTrackList):
        """
        Generate a summary of selected tracks.
        """
        details = await self._extract_details_from_db(track_details)
        prompt = self._load_prompt_from_file("prompts/generate_track_summary.yaml")
        llm = ChatOpenAI(model_name="gpt-4o", temperature=0.3)

        chain = prompt | llm | StrOutputParser()
        stream = chain.astream({"details": details})

        async for response in stream:
            yield response

    async def generate_cms_summary(self, cms_summary_details: CraftMySonicTrackSummary):
        """
        Generate a summary of selected tracks.
        """
        track_details = SelectedTrackList(
            selected_tracks=cms_summary_details.selected_tracks
        )
        details = await self._extract_details_from_db(track_details)
        prompt = self._load_prompt_from_file("prompts/generate_track_summary_cms.yaml")
        llm = ChatOpenAI(model_name="gpt-4o", temperature=0.3)

        chain = prompt | llm | StrOutputParser()
        stream = chain.astream(
            {
                "details": details,
                "title": cms_summary_details.cms_playlist_title,
                "description": cms_summary_details.cms_playlist_description,
            }
        )

        async for response in stream:
            yield response
