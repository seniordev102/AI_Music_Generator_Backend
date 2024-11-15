import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from io import BytesIO
from typing import List

import requests
from fastapi import Depends
from langchain.prompts import load_prompt
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAI as LangChainOpenAI
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.cost.service import CostPerActionService, CostPerActionType
from app.api.credit_management.service import CreditManagementService
from app.common.s3_file_upload import S3FileClient
from app.database import db_session
from app.models import Category, Collection, Track
from app.schemas import SSGenerativeRequest


class SSOracleService:
    def __init__(self, session: AsyncSession = Depends(db_session)) -> None:
        self.session = session
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
        )
        self.logger = logging.getLogger(__name__)
        self.credit_management_service = CreditManagementService(self.session)
        self.cost_per_action_service = CostPerActionService(self.session)

    async def generate_sonic_playlist_details(
        self, ss_generative_data: SSGenerativeRequest, user_email: str
    ) -> dict:
        """
        Generate a title based on the selected sonic supplement track details.
        """
        self.logger.info(
            "Generating title based on the sonic supplement track selection"
        )

        cost_per_action = await self.cost_per_action_service.get_cost_per_action(
            CostPerActionType.SHUFFLE_AND_PLAY_PLAYLIST_GENERATION
        )

        description = f"Sonic Supplement title generation by {user_email} on {datetime.now(timezone.utc)} deducting {cost_per_action.cost} credits"
        await self.credit_management_service.deduct_credits(
            user_email=user_email,
            amount=cost_per_action.cost,
            api_endpoint=cost_per_action.endpoint,
            description=description,
        )

        track_details = await self._extract_details_from_db(ss_generative_data)
        track_details_str = json.dumps(track_details)

        title_generate_task = asyncio.to_thread(
            self._create_title_from_details_sync, track_details_str
        )
        description_generate_task = asyncio.to_thread(
            self._create_description_from_details_sync, track_details_str
        )

        title, description = await asyncio.gather(
            title_generate_task, description_generate_task
        )

        return {
            "title": title,
            "description": description,
        }

    async def generate_cover_image(
        self, ss_generative_data: SSGenerativeRequest, user_email: str
    ) -> dict:
        """
        Create a cover image for the sonic supplement based on the selected values.
        """

        cost_per_action = await self.cost_per_action_service.get_cost_per_action(
            CostPerActionType.SHUFFLE_AND_PLAY_IMAGE_GENERATION
        )

        description = f"Sonic Supplement cover image generation by {user_email} on {datetime.now(timezone.utc)} deducting {cost_per_action.cost} credits"
        await self.credit_management_service.deduct_credits(
            user_email=user_email,
            amount=cost_per_action.cost,
            api_endpoint=cost_per_action.endpoint,
            description=description,
        )

        track_details = await self._extract_details_from_db(ss_generative_data)
        track_details_str = json.dumps(track_details)
        image_prompt = self._create_image_prompt_from_details_sync(
            track_details=track_details_str
        )
        ai_image_url = self._generate_images_from_ai_sync(
            image_prompt=image_prompt, size="1792x1024"
        )
        cover_image_details = await self._process_and_upload_image(
            image_url=ai_image_url,
            file_prefix="ss",
            folder_name="sonic_supplements",
            reduction_factor=4,
        )
        return {
            "image_details": cover_image_details,
            "prompt": image_prompt,
        }

    async def generate_square_image(
        self, ss_generative_data: SSGenerativeRequest, user_email: str
    ) -> dict:
        """
        Create a cover image for the sonic supplement based on the selected values.
        """
        cost_per_action = await self.cost_per_action_service.get_cost_per_action(
            CostPerActionType.SHUFFLE_AND_PLAY_IMAGE_GENERATION
        )

        description = f"Sonic Supplement square image generation by {user_email} on {datetime.now(timezone.utc)} deducting {cost_per_action.cost} credits"
        await self.credit_management_service.deduct_credits(
            user_email=user_email,
            amount=cost_per_action.cost,
            api_endpoint=cost_per_action.endpoint,
            description=description,
        )

        track_details = await self._extract_details_from_db(ss_generative_data)
        track_details_str = json.dumps(track_details)
        image_prompt = self._create_image_prompt_from_details_sync(
            track_details=track_details_str
        )
        ai_image_url = self._generate_images_from_ai_sync(
            image_prompt=image_prompt, size="1024x1024"
        )
        cover_image_details = await self._process_and_upload_image(
            image_url=ai_image_url,
            file_prefix="ss",
            folder_name="sonic_supplements",
            reduction_factor=4,
        )
        return {
            "image_details": cover_image_details,
            "prompt": image_prompt,
        }

    def _create_title_from_details_sync(self, details: str) -> dict:
        prompt = self._load_prompt_from_file("prompts/generate_ss_title.yaml")
        llm = ChatOpenAI(model_name="gpt-4o", temperature=1)

        chain = prompt | llm | StrOutputParser()
        response = chain.invoke({"details": details})
        return response

    def _create_description_from_details_sync(self, details: str) -> dict:
        prompt = self._load_prompt_from_file(
            "prompts/generate_ss_title_description.yaml"
        )
        llm = ChatOpenAI(model_name="gpt-4o", temperature=1)

        chain = prompt | llm | StrOutputParser()
        response = chain.invoke({"details": details})
        return response

    def _create_image_prompt_from_details_sync(self, track_details: str) -> dict:
        """
        Generate an image prompt based on the details of the sonic supplement.
        """
        prompt = self._load_prompt_from_file("prompts/generate_ss_image_prompt.yaml")
        llm = ChatOpenAI(model_name="gpt-4o", temperature=1)

        chain = prompt | llm | StrOutputParser()
        response = chain.invoke({"details": track_details})
        return response

    async def _extract_details_from_db(
        self, selected_values: SSGenerativeRequest
    ) -> dict:
        """
        Extract details from the selected values of the sonic supplement request.
        """

        async def fetch_category() -> Category:
            category_record = await self.session.execute(
                select(Category).where(Category.id == selected_values.selected_category)
            )
            return category_record.scalars().first()

        async def fetch_collection() -> Collection:
            collection_record = await self.session.execute(
                select(Collection).where(
                    Collection.id == selected_values.selected_collection
                )
            )
            return collection_record.scalars().first()

        async def fetch_tracks() -> List[Track]:
            track_records = await self.session.execute(
                select(Track).where(Track.id.in_(selected_values.selected_tracks))
            )
            return track_records.scalars().all()

        # Run all three queries concurrently
        selected_category, selected_collection, selected_tracks = await asyncio.gather(
            fetch_category(), fetch_collection(), fetch_tracks()
        )

        category_details = {
            "name": selected_category.name,
            "description": selected_category.description,
        }

        collection_details = {
            "name": selected_collection.name,
            "description": selected_collection.description,
            "short_description": selected_collection.short_description,
        }

        track_details = [
            {
                "name": track.name,
                "description": track.description,
                "short_description": track.short_description,
                "frequency_meaning": track.frequency_meaning,
            }
            for track in selected_tracks
        ]

        return {
            "category_details": category_details,
            "collection_details": collection_details,
            "track_details": track_details,
        }

    def _generate_images_from_ai_sync(self, image_prompt: str, size: str) -> dict:
        """
        Generate images based on the given image prompt and upload them to an S3 bucket.
        """
        llm = LangChainOpenAI(temperature=0.9)
        prompt = self._load_prompt_from_file("prompts/image_generation_prompt.yaml")
        chain = RunnableParallel({"image_desc": RunnablePassthrough()}) | prompt | llm
        image_url = DallEAPIWrapper(
            model="dall-e-3",
            size=size,
        ).run(chain.invoke(image_prompt))

        return image_url

    async def generate_sonic_supplement_spread_summary(
        self, selected_details: SSGenerativeRequest, user_email: str
    ):
        """
        Generate a sonic supplement spread summary based on the selected track details.
        """
        cost_per_action = await self.cost_per_action_service.get_cost_per_action(
            CostPerActionType.SONIC_SUMMARY_GENERATION
        )

        description = f"Sonic Supplement spread summary generation by {user_email} on {datetime.now(timezone.utc)} deducting {cost_per_action.cost} credits"
        await self.credit_management_service.deduct_credits(
            user_email=user_email,
            amount=cost_per_action.cost,
            api_endpoint=cost_per_action.endpoint,
            description=description,
        )

        details = await self._extract_details_from_db(selected_details)
        prompt = self._load_prompt_from_file("prompts/generate_ss_spread_summary.yaml")
        llm = ChatOpenAI(model_name="gpt-4o", temperature=1)

        chain = prompt | llm | StrOutputParser()
        stream = chain.astream({"details": details})

        async for response in stream:
            yield response

    async def _process_and_upload_image(
        self,
        image_url: str,
        file_prefix: str,
        folder_name: str,
        reduction_factor: int,
        quality: int = 100,
    ) -> str:
        try:
            response = requests.get(image_url)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content))
                # save original image and thumbnail image both and upload both file to s3

                # save original file to temp folder
                file_name_original = f"{file_prefix}_{int(time.time())}.png"
                output_dir = "tmp"
                output_path_original = os.path.join(output_dir, file_name_original)
                os.makedirs(output_dir, exist_ok=True)
                img.save(output_path_original, format="PNG", quality=quality)

                # resize image
                new_width = img.width // reduction_factor
                new_height = img.height // reduction_factor
                img = img.resize((new_width, new_height), Image.LANCZOS)
                file_name_resize = f"{file_prefix}_thumb_{int(time.time())}.png"
                output_dir = "tmp"
                output_path_resize = os.path.join(output_dir, file_name_resize)
                os.makedirs(output_dir, exist_ok=True)
                img.save(output_path_resize, format="PNG", quality=quality)

                file_content_resize = None
                file_content_original = None

                # upload both files to s3
                s3_client = S3FileClient()
                with open(output_path_resize, "rb") as f:
                    file_content_resize = f.read()

                with open(output_path_original, "rb") as f:
                    file_content_original = f.read()

                # upload file to s3
                file_upload_tasks_resized = asyncio.to_thread(
                    s3_client.upload_file_from_buffer,
                    file_name=file_name_resize,
                    folder_name=folder_name,
                    file_content=file_content_resize,
                    content_type="image/png",
                )

                file_upload_tasks_original = asyncio.to_thread(
                    s3_client.upload_file_from_buffer,
                    file_name=file_name_original,
                    folder_name=folder_name,
                    file_content=file_content_original,
                    content_type="image/png",
                )

                # Run the upload tasks concurrently
                thumbnail_image, original_image = await asyncio.gather(
                    file_upload_tasks_resized, file_upload_tasks_original
                )

                # remove file from temp folder
                if os.path.exists(output_path_resize):
                    os.remove(output_path_resize)
                    self.logger.info(
                        f"Deleted the resized image at {output_path_resize}"
                    )

                if os.path.exists(output_path_original):
                    os.remove(output_path_original)
                    self.logger.info(
                        f"Deleted the original image at {output_path_original}"
                    )

                return {
                    "thumbnail_image": thumbnail_image,
                    "original_image": original_image,
                }

        except Exception as e:
            self.logger.error(f"Error uploading file to S3: {e}")

    def _load_prompt_from_file(self, file_path: str):
        """
        Load a prompt from a specified file path.
        """
        script_path = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_path)
        target_file_path = os.path.join(script_dir, file_path)
        return load_prompt(target_file_path)
