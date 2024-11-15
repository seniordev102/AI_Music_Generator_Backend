import asyncio
import json
import os
import random
import time
import uuid as uuid_pkg
from io import BytesIO
from typing import List

import requests
from fastapi import Depends, status
from langchain.prompts import load_prompt
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAI as LangChainOpenAI
from langchain_openai import OpenAIEmbeddings
from langfuse import Langfuse
from langfuse.callback import CallbackHandler
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.s3_file_upload import S3FileClient
from app.config import settings
from app.database import db_session
from app.logger.logger import logger
from app.models import Collection, SonicIVCollections, Track, TrackEmbedding
from app.schemas import GenerateSonicIVDetails


class SonicIVOracleService:
    def __init__(self, session: AsyncSession = Depends(db_session)) -> None:
        self.session = session
        self.settings = settings
        self.langfuse = Langfuse(
            secret_key=self.settings.LANGFUSE_SECRET_KEY,
            public_key=self.settings.LANGFUSE_PUBLIC_KEY,
            host=self.settings.LANGFUSE_HOST,
        )

    def _load_prompt_from_file(self, file_path: str):
        """
        Load a prompt from a specified file path.
        """
        script_path = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_path)
        target_file_path = os.path.join(script_dir, file_path)
        return load_prompt(target_file_path)

    async def generate_sonic_iv_details(
        self, sonic_iv_details: GenerateSonicIVDetails
    ) -> dict:
        logger.info("Generating title and description for the craft my sonic playlist")

        track_details = await self._extract_track_details(
            sonic_iv_details.selected_tracks
        )
        track_details_str = json.dumps(track_details)

        title_generate_task = asyncio.to_thread(
            self._create_title_from_details,
            track_details=track_details_str,
            user_prompt=sonic_iv_details.user_prompt,
            user_title=sonic_iv_details.title if sonic_iv_details.title else "",
        )

        description_generate_task = asyncio.to_thread(
            self._create_description_from_details,
            track_details=track_details_str,
            user_prompt=sonic_iv_details.user_prompt,
            user_title=sonic_iv_details.title if sonic_iv_details.title else "",
        )

        title, description = await asyncio.gather(
            title_generate_task, description_generate_task
        )
        return {
            "title": title,
            "description": description,
        }

    async def generate_sonic_iv_images(self, user_prompt: str) -> dict:
        logger.info("Generating images for the sonic iv playlist")

        cover_image_task = asyncio.to_thread(
            self._generate_images_from_ai_sync, user_prompt, "1792x1024"
        )
        square_cover_image_task = asyncio.to_thread(
            self._generate_images_from_ai_sync, user_prompt, "1024x1024"
        )

        cover_image_url, square_cover_image_url = await asyncio.gather(
            cover_image_task, square_cover_image_task
        )

        cover_image_upload_task = self._process_and_upload_image(
            image_url=cover_image_url,
            file_prefix="sonic-iv-cover",
            folder_name="sonic-iv",
            reduction_factor=4,
            quality=100,
        )

        square_image_upload_task = self._process_and_upload_image(
            image_url=square_cover_image_url,
            file_prefix="sonic-iv-square",
            folder_name="sonic-iv",
            reduction_factor=4,
            quality=100,
        )

        square_image_details, cover_image_details = await asyncio.gather(
            square_image_upload_task, cover_image_upload_task
        )

        return {
            "square_image_details": square_image_details,
            "cover_image_details": cover_image_details,
        }

    async def generate_sonic_iv_cover_image(self, user_prompt: str) -> dict:
        logger.info("Generating cover image for the sonic iv playlist")

        cover_image_url = self._generate_images_from_ai_sync(user_prompt, "1792x1024")

        cover_image_details = await self._process_and_upload_image(
            image_url=cover_image_url,
            file_prefix="sonic-iv-cover",
            folder_name="sonic-iv",
            reduction_factor=4,
            quality=100,
        )

        return cover_image_details

    async def generate_sonic_iv_square_image(self, user_prompt: str) -> dict:
        logger.info("Generating square image for the sonic iv playlist")

        square_cover_image_url = self._generate_images_from_ai_sync(
            user_prompt, "1024x1024"
        )

        square_image_details = await self._process_and_upload_image(
            image_url=square_cover_image_url,
            file_prefix="sonic-iv-square",
            folder_name="sonic-iv",
            reduction_factor=4,
            quality=100,
        )

        return square_image_details

    def _generate_craft_my_sonic_square_image_sync(self, user_prompt: str, size: str):
        """
        Generate images from the AI based on the user prompt.
        """
        try:
            logger.info("Generating images from AI")

            llm = LangChainOpenAI(temperature=0.9)
            prompt = self._load_prompt_from_file(
                "prompts/generate_cms_square_image.yaml"
            )
            chain = (
                RunnableParallel({"user_prompt": RunnablePassthrough()}) | prompt | llm
            )
            image_url = DallEAPIWrapper(
                model="dall-e-3",
                size=size,
            ).run(chain.invoke({"user_prompt": user_prompt}))

            return image_url
        except Exception as e:
            logger.error(f"Failed to generate images from AI: {e}")
            return None

    def _generate_images_from_ai_sync(self, user_prompt: str, size: str):
        try:
            logger.info("Generating images from AI")

            credit_amount = 1
            if size == "1792x1024":
                credit_amount = 2
            elif size == "1024x1024":
                credit_amount = 1

            trace = self.langfuse.trace(
                name="Craft My Song Image Generation",
                trace_id=str(uuid_pkg.uuid4()),
                input={
                    "user_prompt": user_prompt,
                    "size": size,
                },
                metadata={
                    "size": size,
                },
                tags=["image-generation", "craft-my-song"],
            )

            generation = trace.generation(
                name="Craft My Song Image Generation",
                input={
                    "user_prompt": user_prompt,
                    "size": size,
                },
                model="dalle-3",
                metadata={
                    "size": size,
                },
                usage={"input": credit_amount},
            )

            llm = LangChainOpenAI(temperature=0.9)
            prompt = self._load_prompt_from_file("prompts/generate_cms_image.yaml")
            chain = (
                RunnableParallel({"user_prompt": RunnablePassthrough()}) | prompt | llm
            )
            image_url = DallEAPIWrapper(
                model="dall-e-3",
                size=size,
            ).run(chain.invoke({"user_prompt": user_prompt}))

            generation.end(
                output={"image_url": image_url},
                status_message=status.HTTP_200_OK,
            )

            return image_url
        except Exception as e:
            logger.error(f"Failed to generate images from AI: {e}")
            return None

    def _create_title_from_details(
        self, track_details: str, user_prompt: str, user_title: str
    ) -> dict:
        """
        Generate a title from the extracted details of the craft my sonic.
        """
        prompt = self._load_prompt_from_file("prompts/generate_cms_title.yaml")
        llm = ChatOpenAI(
            model_name="gpt-4o",
            temperature=1,
            callbacks=[
                CallbackHandler(
                    trace_name="Sonic Infusions Title Generator",
                    metadata={
                        "track_details": track_details,
                        "user_prompt": user_prompt,
                        "user_title": user_title,
                    },
                )
            ],
        )
        chain = prompt | llm | StrOutputParser()
        response = chain.invoke(
            {
                "track_details": track_details,
                "user_prompt": user_prompt,
                "user_title": user_title,
            }
        )
        return response

    def _create_description_from_details(
        self, track_details: str, user_prompt, user_title: str
    ) -> dict:
        """
        Generate a description from the extracted details of the craft my sonic.
        """
        prompt = self._load_prompt_from_file("prompts/generate_cms_description.yaml")
        llm = ChatOpenAI(
            model_name="gpt-4o",
            temperature=1,
            callbacks=[
                CallbackHandler(
                    trace_name="Sonic Infusions Title Generator",
                    metadata={
                        "track_details": track_details,
                        "user_prompt": user_prompt,
                        "user_title": user_title,
                    },
                )
            ],
        )

        chain = prompt | llm | StrOutputParser()
        response = chain.invoke(
            {
                "track_details": track_details,
                "user_prompt": user_prompt,
                "user_title": user_title,
            }
        )
        return response

    async def _extract_track_details(
        self, selected_tracks_ids: List[uuid_pkg.UUID]
    ) -> dict:
        """
        Extract track details based on id list.
        """

        # Get all the track details
        track_records = await self.session.execute(
            select(Track).where(Track.id.in_(selected_tracks_ids))
        )
        selected_tracks: List[Track] = track_records.scalars().all()

        track_details = []
        for track in selected_tracks:

            # Get the collection details
            collection_record = await self.session.execute(
                select(Collection).where(Collection.id == track.collection_id)
            )
            selected_collection: Collection = collection_record.scalars().first()
            track_details.append(
                {
                    "name": track.name,
                    "description": track.description,
                    "short_description": track.short_description,
                    "frequency_meaning": track.frequency_meaning,
                    "collection_name": selected_collection.name,
                    "collection_description": selected_collection.description,
                }
            )

        return track_details

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
                    logger.info(f"Deleted the resized image at {output_path_resize}")

                if os.path.exists(output_path_original):
                    os.remove(output_path_original)
                    logger.info(f"Deleted the original image at {output_path_original}")

                return {
                    "thumbnail_image": thumbnail_image,
                    "original_image": original_image,
                }

        except Exception as e:
            logger.error(f"Error uploading file to S3: {e}")

    async def retrieve_related_tracks_for_sonic_iv(
        self, user_prompt: str, k: int = 20
    ) -> List[str]:

        # get sonic iv collections ids
        query = select(SonicIVCollections).limit(1)

        sonic_iv_records = await self.session.execute(query)
        sonic_iv: SonicIVCollections = sonic_iv_records.scalar_one_or_none()

        collection_ids = (
            sonic_iv.collection_ids.split(",") if sonic_iv.collection_ids else []
        )

        # Step 2: Generate the embedding for the user prompt
        embeddings = OpenAIEmbeddings()
        query_embedding = embeddings.embed_query(user_prompt)

        # Step 3: Perform similarity search on the track_embeddings table
        result = await self.session.execute(
            select(
                TrackEmbedding.track_id,
                TrackEmbedding.embedding.cosine_distance(query_embedding).label(
                    "distance"
                ),
            )
            .where(TrackEmbedding.collection_id.in_(collection_ids))
            .order_by("distance")
            .limit(k)
        )

        # Step 4: Fetch the track IDs and convert them to strings
        similar_track_ids = [str(row.track_id) for row in result.fetchall()]

        similar_track_ids = similar_track_ids[:5]

        # Step 5: Randomize the track IDs (if needed)
        random.shuffle(similar_track_ids)

        return similar_track_ids
