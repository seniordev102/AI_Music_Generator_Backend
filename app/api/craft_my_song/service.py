import io
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import requests
from fastapi import BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain.prompts import ChatPromptTemplate, load_prompt
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAI as LangChainOpenAI
from langfuse import Langfuse
from langfuse.callback import CallbackHandler
from PIL import Image
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.cost.service import CostPerActionService, CostPerActionType
from app.api.credit_management.service import CreditManagementService
from app.common.http_response_model import PageMeta
from app.common.s3_file_upload import S3FileClient
from app.config import settings
from app.database import db_session
from app.logger.logger import logger
from app.models import IAHCraftMySong, MusicRequestStatus, User
from app.schemas import (
    CountType,
    CraftMySongEditRequest,
    CreateCraftMySong,
    GenerateLyrics,
)


class CraftMySongService:
    def __init__(self, session: AsyncSession = Depends(db_session)) -> str:
        self.session = session
        self.settings = settings
        self.cost_per_action_service = CostPerActionService(session)
        self.credit_management_service = CreditManagementService(session)
        self.langfuse = Langfuse(
            secret_key=self.settings.LANGFUSE_SECRET_KEY,
            public_key=self.settings.LANGFUSE_PUBLIC_KEY,
            host=self.settings.LANGFUSE_HOST,
        )

    def _load_prompt_from_file_path(self, file_path: str):
        script_path = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_path)
        target_file_path = os.path.join(script_dir, file_path)
        return load_prompt(target_file_path)

    async def generate_song_from_user_input(
        self,
        email: str,
        request_payload: CreateCraftMySong,
        background_tasks: BackgroundTasks,
    ):
        trace_id = str(uuid.uuid4())
        trace = self.langfuse.trace(
            name="RFM Song Generation",
            trace_id=trace_id,
            input={
                "email": email,
                "user_prompt": request_payload.user_prompt,
            },
            tags=["music-generation", "rfm"],
            user_id=email,
            metadata={
                "request_payload": request_payload.dict(),
            },
        )

        # get the user from the email address
        email_lower_case = email.lower()
        user_record = await self.session.execute(
            select(User).where(User.email == email_lower_case)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # reduce llm cost per action
        cost_per_action = await self.cost_per_action_service.get_cost_per_action(
            CostPerActionType.RFM_SONG_GENERATION
        )

        # deduct credits from user
        description = f"RFM Song generation by {user.email} on {datetime.now(timezone.utc)} deducting {cost_per_action.cost} credits"
        await self.credit_management_service.deduct_credits(
            user_email=user.email,
            amount=cost_per_action.cost,
            api_endpoint=cost_per_action.endpoint,
            description=description,
        )

        has_8_count = False
        url = None
        if request_payload.genres:
            genres_list = request_payload.genres.lower().split(",")
            has_8_count = any(
                "8-count" in genre.strip().lower() for genre in genres_list
            )

        if has_8_count:
            url = f"{self.settings.MUSIC_GENERATOR_API_URL}/generate-cheer-track"
            logger.debug(f"Generating 8-count song")
        else:
            # send request to the music generator
            url = f"{self.settings.MUSIC_GENERATOR_API_URL}/generate-music"
            logger.debug(f"Generating song")

        generation = trace.generation(
            name="RFM Song Generation",
            input={
                "is_vocal": request_payload.is_vocal,
                "voice": request_payload.voice_type,
                "user_prompt": request_payload.user_prompt,
                "style": request_payload.song_style,
                "genres": request_payload.genres,
                "vibes": request_payload.vibes,
                "tempo": request_payload.tempo,
                "instruments": request_payload.instruments,
                "length": request_payload.length,
            },
            usage={"input": 1},
            model="iah-music-generator",
        )

        payload = json.dumps(
            {
                "is_vocal": request_payload.is_vocal,
                "voice": request_payload.voice_type,
                "user_prompt": request_payload.user_prompt,
                "style": request_payload.song_style,
                "genres": request_payload.genres,
                "vibes": request_payload.vibes,
                "tempo": request_payload.tempo,
                "instruments": request_payload.instruments,
                "length": request_payload.length,
            }
        )
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Token {self.settings.MUSIC_GENERATOR_API_KEY}",
        }
        response = requests.request("POST", url, headers=headers, data=payload)

        if response.status_code != status.HTTP_200_OK:
            logger.error(
                f"Error while requesting AI music generation: {response.json()}"
            )
            generation.end(
                output={
                    "error": response.json(),
                },
                status_message=status.HTTP_400_BAD_REQUEST,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error while requesting AI music generation",
            )

        # get the response
        music_gen_response = response.json()
        request_id = music_gen_response["id"]

        generation.end(
            output={
                "request_id": request_id,
            },
            status_message=status.HTTP_200_OK,
        )

        self.langfuse.flush()

        # save data into the database
        craft_my_song = IAHCraftMySong(
            title=request_payload.title,
            request_id=request_id,
            user_id=user.id,
            request_status=MusicRequestStatus.PENDING,
            user_prompt=request_payload.user_prompt,
            song_style=request_payload.song_style,
            is_private=request_payload.is_private,
            is_vocal=request_payload.is_vocal,
            voice_type=request_payload.voice_type,
            genres=request_payload.genres,
            cover_image_status=MusicRequestStatus.PENDING,
            generated_timestamp=int(time.time()),
        )

        self.session.add(craft_my_song)
        await self.session.commit()

        # Add album art generation as a background task
        background_tasks.add_task(
            self._process_album_art_background, craft_my_song.id, user.email, request_id
        )

        return craft_my_song

    async def get_generated_tracks_by_user(self, email: str, page: int, page_size: int):
        # get the user from the email address
        email_lower_case = email.lower()
        user_record = await self.session.execute(
            select(User).where(User.email == email_lower_case)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        tracks_to_skip = (page - 1) * page_size

        # Get total number of items
        total_items = await self.session.execute(
            select(func.count())
            .select_from(IAHCraftMySong)
            .where(IAHCraftMySong.user_id == user.id)
        )
        total_items = total_items.scalar()

        # Calculate total pages
        total_pages = -(-total_items // page_size)

        # Fetch paginated items
        gen_track_list = await self.session.execute(
            select(IAHCraftMySong)
            .where(IAHCraftMySong.user_id == user.id)
            .offset(tracks_to_skip)
            .order_by(IAHCraftMySong.created_at.desc())
            .limit(page_size)
        )
        tracks = gen_track_list.scalars().fetchall()

        return tracks, PageMeta(
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            total_items=total_items,
        )

    async def requesting_status_update(self, email: str, request_id: str):
        # get the user from the email address
        email_lower_case = email.lower()
        user_record = await self.session.execute(
            select(User).where(User.email == email_lower_case)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # fetch the track details by the request id
        track_record = await self.session.execute(
            select(IAHCraftMySong).where(IAHCraftMySong.request_id == request_id)
        )

        gen_track: IAHCraftMySong = track_record.scalar_one_or_none()

        if not gen_track:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Generated track not found for given request id",
            )

        if (
            gen_track.request_status == MusicRequestStatus.READY
            and gen_track.music_url != None
        ):
            logger.debug(f"Requested track id status is ready returning object ")
            return gen_track

        # requesting for the new status update from the api
        logger.debug(f"Requesting for updated request from API")
        url = f"{self.settings.MUSIC_GENERATOR_API_URL}/get-music/{request_id}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Token {self.settings.MUSIC_GENERATOR_API_KEY}",
        }
        response = requests.get(url, headers=headers)

        if response.status_code != status.HTTP_200_OK:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error while requesting status update",
            )

        music_gen_response = response.json()
        music_status = music_gen_response.get("status", MusicRequestStatus.PENDING)
        clips = music_gen_response.get("clips", [])

        streaming_url = None
        music_url = None
        music_url_v2 = None
        streaming_url_v2 = None

        if clips and len(clips) > 0:
            first_item = clips[0]
            streaming_url = first_item.get("streaming", None)
            music_url = first_item.get("s3_url", None)

            # Only try to access the second item if it exists
            if len(clips) > 1:
                second_item = clips[1]
                streaming_url_v2 = second_item.get("streaming", None)
                music_url_v2 = second_item.get("s3_url", None)

        if music_status == "ready":
            gen_track.request_status = MusicRequestStatus.READY

        gen_track.music_url = music_url
        gen_track.streaming_url = streaming_url
        gen_track.music_url_v2 = music_url_v2
        gen_track.streaming_url_v2 = streaming_url_v2

        if music_status == "failed":
            gen_track.request_status = MusicRequestStatus.ERROR

        if music_status == "in-progress":
            if gen_track.generated_timestamp != None:
                if gen_track.generated_timestamp < int(time.time()) - 5 * 60:
                    gen_track.request_status = MusicRequestStatus.ERROR

        await self.session.commit()

        return gen_track

    async def generate_lyrics(
        self,
        user_request: GenerateLyrics,
        user_email: str,
    ):
        langfuse_prompt = self.langfuse.get_prompt(
            "rfm-lyrics-generator", label="latest", cache_ttl_seconds=100
        )

        langchain_prompt = ChatPromptTemplate.from_template(
            langfuse_prompt.get_langchain_prompt(),
            metadata={"langfuse_prompt": langfuse_prompt},
        )

        model = langfuse_prompt.config["model"]
        temperature = str(langfuse_prompt.config["temperature"])

        functions = [
            {
                "name": "format_lyrics",
                "description": "Format the generated lyrics and title into a structured object",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "The generated title of the song.",
                        },
                        "lyrics": {
                            "type": "string",
                            "description": "The generated lyrics of the song.",
                        },
                    },
                    "required": ["title", "lyrics"],
                },
            }
        ]

        # reduce llm cost per action
        cost_per_action = await self.cost_per_action_service.get_cost_per_action(
            CostPerActionType.RFM_LYRICS_GENERATION
        )

        # deduct credits from user
        description = f"RFM Lyrics generation by {user_email} on {datetime.now(timezone.utc)} deducting {cost_per_action.cost} credits"
        await self.credit_management_service.deduct_credits(
            user_email=user_email,
            amount=cost_per_action.cost,
            api_endpoint=cost_per_action.endpoint,
            description=description,
        )

        chat = ChatOpenAI(
            model=model,
            temperature=float(temperature),
            model_kwargs={
                "functions": functions,
                "function_call": {"name": "format_lyrics"},
            },
            callbacks=[
                CallbackHandler(
                    trace_name="RFM Lyrics Generator",
                    user_id=user_email,
                )
            ],
        )

        chain = langchain_prompt | chat

        # Create input variables dictionary from user_request
        input_variables = {
            "user_prompt": user_request.user_prompt,
            "genres": user_request.genres or "",
            "song_style": user_request.song_style or "",
            "vibe": user_request.vibe or "",
            "tempo": user_request.tempo or "",
            "instruments": user_request.instruments or "",
            "length": str(user_request.length) if user_request.length else "",
        }

        response = chain.invoke(input_variables)
        function_call = response.additional_kwargs.get("function_call")
        if function_call:
            arguments_str = function_call.get("arguments", "")
            arguments = json.loads(arguments_str)
            title = arguments.get("title", "")
            lyrics = arguments.get("lyrics", "")
            return {"title": title, "lyrics": lyrics}
        else:
            return {"title": "Untitled", "lyrics": response.content}

    async def _generate_album_art(
        self,
        user_prompt: str,
        music_style: str,
        music_genres: str,
        user_email: str,
        request_id: str,
    ) -> None:

        llm = LangChainOpenAI(temperature=0.9)
        prompt = self._load_prompt_from_file_path(
            "prompts/image_generation_prompt.yaml"
        )

        # reduce llm cost per action
        cost_per_action = await self.cost_per_action_service.get_cost_per_action(
            CostPerActionType.RFM_IMAGE_GENERATION
        )

        # deduct credits from user
        description = f"RFM song album art image generation by {user_email} on {datetime.now(timezone.utc)} deducting {cost_per_action.cost} credits"
        await self.credit_management_service.deduct_credits(
            user_email=user_email,
            amount=cost_per_action.cost,
            api_endpoint=cost_per_action.endpoint,
            description=description,
        )
        # Create input data matching prompt template variables
        input_data = {
            "user_prompt": user_prompt,
            "music_style": music_style,
            "music_genres": music_genres,
        }

        trace = self.langfuse.trace(
            name="RFM Album Art Generation",
            trace_id=str(uuid.uuid4()),
            input={
                "user_email": user_email,
            },
            metadata={
                "request_id": request_id,
            },
            tags=["image-generation", "rfm"],
            user_id=user_email,
        )

        generation = trace.generation(
            name="RFM Song Album Art Generation",
            input=input_data,
            model="dalle-3",
            metadata={
                "request_id": request_id,
            },
            usage={"input": 1},
        )

        chain = prompt | llm

        image_url = DallEAPIWrapper(
            model="dall-e-3",
            size="1024x1024",
        ).run(chain.invoke(input_data))

        generation.end(
            output={
                "image_url": image_url,
            },
            status_message=status.HTTP_200_OK,
        )

        # download the image and upload into the s3 bucket
        s3Client = S3FileClient()

        # generate a file name using timestamp
        file_name = f"craft_my_song_album_{int(time.time())}.png"
        image_url_s3 = await s3Client.upload_image_from_url(
            image_url, file_name, "image/png"
        )

        return {"image": image_url_s3}

    async def _process_album_art_background(
        self, craft_my_song_id: int, user_email: str, request_id: str
    ):
        try:

            # Get the record from database
            query = select(IAHCraftMySong).where(IAHCraftMySong.id == craft_my_song_id)
            record = await self.session.execute(query)
            craft_my_song = record.scalar_one_or_none()

            if not craft_my_song:
                logger.error(
                    f"Could not find craft_my_song record with id {craft_my_song_id}"
                )
                return

            # Generate the album art
            image_response = await self._generate_album_art(
                user_prompt=craft_my_song.user_prompt,
                music_style=craft_my_song.song_style,
                music_genres=craft_my_song.genres,
                user_email=user_email,
                request_id=request_id,
            )

            original_image_url = image_response["image"]
            original_filename = original_image_url.split("/")[-1]

            # Generate thumbnail
            thumbnail_url = await self._generate_thumbnail(
                original_image_url, original_filename
            )

            # Update the record with both URLs
            craft_my_song.music_cover_image_url = original_image_url
            craft_my_song.music_cover_image_thumbnail_url = thumbnail_url
            craft_my_song.cover_image_status = MusicRequestStatus.FINISHED
            await self.session.commit()

            logger.info(
                f"Successfully generated and updated album art and thumbnail for craft_my_song id {craft_my_song_id}"
            )

        except Exception as e:
            logger.error(
                f"Error processing album art for craft_my_song id {craft_my_song_id}: {str(e)}"
            )
            # Update the record with error status
            try:
                craft_my_song.cover_image_status = MusicRequestStatus.ERROR
                await self.session.commit()
            except:
                await self.session.rollback()

    async def _generate_thumbnail(self, image_url: str, filename: str) -> str:
        try:
            # Download the image
            response = requests.get(image_url)
            response.raise_for_status()

            # Open the image using PIL
            image = Image.open(io.BytesIO(response.content))

            # Create thumbnail while maintaining aspect ratio
            image.thumbnail((300, 300), Image.Resampling.LANCZOS)

            # Convert to RGB if image is in RGBA mode
            if image.mode == "RGBA":
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[3])
                image = background

            # Save to bytes buffer
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=95, optimize=True)
            buffer.seek(0)

            # Generate thumbnail filename
            thumbnail_filename = f"thumb_{filename}"

            # Upload to S3
            s3Client = S3FileClient()
            thumbnail_url = s3Client.upload_file_from_buffer(
                file_name=thumbnail_filename,
                folder_name="ai-album-art",
                file_content=buffer.getvalue(),
                content_type="image/jpeg",
            )

            if not thumbnail_url:
                raise Exception("Failed to upload thumbnail to S3")

            return thumbnail_url

        except Exception as e:
            logger.error(f"Error generating thumbnail: {str(e)}")
            raise

    async def delete_craft_my_song_by_id(self, user_email: str, song_id: str) -> bool:
        # Retrieve user by email
        craft_my_song = await self._get_craft_my_song_editable_instance(
            user_email=user_email, song_id=song_id
        )
        await self.session.delete(craft_my_song)
        await self.session.commit()
        return True

    async def update_craft_my_song_details(
        self, user_email: str, song_id: str, song_data: CraftMySongEditRequest
    ) -> IAHCraftMySong:
        craft_my_song = await self._get_craft_my_song_editable_instance(
            user_email=user_email, song_id=song_id
        )

        update_data = {k: v for k, v in song_data.dict().items() if v is not None}

        if update_data:
            await self.session.execute(
                update(IAHCraftMySong)
                .where(IAHCraftMySong.id == song_id)
                .values(**update_data)
            )
            await self.session.commit()

            # Refresh the song object with updated data
            await self.session.refresh(craft_my_song)

        return craft_my_song

    async def update_song_statistics(
        self, user_email: str, song_id: str, update_type: CountType
    ) -> IAHCraftMySong:
        # Retrieve user by email
        user_query = select(User).where(User.email == user_email)
        user_result = await self.session.execute(user_query)
        user: User = user_result.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                detail="User not found", status_code=status.HTTP_404_NOT_FOUND
            )

        # Retrieve the song by ID
        song_query = select(IAHCraftMySong).where(IAHCraftMySong.id == song_id)
        song_result = await self.session.execute(song_query)
        craft_my_song: IAHCraftMySong = song_result.scalar_one_or_none()

        if craft_my_song is None:
            raise HTTPException(
                detail="Sorry, the song you requested isn't available",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Ensure the user owns the song
        if craft_my_song.user_id != user.id:
            if update_type == CountType.LIKE:
                craft_my_song.likes_count = (craft_my_song.likes_count or 0) + 1

            elif update_type == CountType.SHARE:
                craft_my_song.shares_count = (craft_my_song.shares_count or 0) + 1

            elif update_type == CountType.PLAY:
                craft_my_song.plays_count = (craft_my_song.plays_count or 0) + 1
        else:
            logger.debug(
                "Skipping Song statistics can only be updated by other users, not the song owner"
            )

        await self.session.commit()
        await self.session.refresh(craft_my_song)
        return craft_my_song

    async def update_song_cover_image(
        self, user_email: str, song_id: str, user_prompt: str
    ) -> IAHCraftMySong:

        craft_my_song = await self._get_craft_my_song_editable_instance(
            user_email=user_email, song_id=song_id
        )
        # Generate the album art
        image_response = await self._generate_album_art(
            user_prompt=user_prompt,
            music_style=craft_my_song.song_style,
            music_genres=craft_my_song.genres,
            user_email=user_email,
        )

        original_image_url = image_response["image"]
        original_filename = original_image_url.split("/")[-1]

        # Generate thumbnail
        thumbnail_url = await self._generate_thumbnail(
            original_image_url, original_filename
        )

        craft_my_song.music_cover_image_url = original_image_url
        craft_my_song.music_cover_image_thumbnail_url = thumbnail_url

        await self.session.commit()
        await self.session.refresh(craft_my_song)

        return craft_my_song

    async def _get_craft_my_song_editable_instance(
        self, user_email: str, song_id: str
    ) -> IAHCraftMySong:
        # Retrieve user by email
        user_query = select(User).where(User.email == user_email)
        user_result = await self.session.execute(user_query)
        user: User = user_result.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                detail="User not found", status_code=status.HTTP_404_NOT_FOUND
            )

        # Retrieve the song by ID
        song_query = select(IAHCraftMySong).where(IAHCraftMySong.id == song_id)
        song_result = await self.session.execute(song_query)
        craft_my_song: IAHCraftMySong = song_result.scalar_one_or_none()

        if craft_my_song is None:
            raise HTTPException(
                detail="Sorry, the song you requested isn't available",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Ensure the user owns the song
        if craft_my_song.user_id != user.id:
            raise HTTPException(
                detail="You don't have permission to update song details",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        return craft_my_song

    async def _fetch_audio_stream(self, url: str) -> bytes:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Could not fetch the audio file",
                )
            return response.content

    async def download_song(
        self, song_id: str, user_email: str, version: int
    ) -> StreamingResponse:
        craft_my_song = await self._get_craft_my_song_editable_instance(
            user_email=user_email, song_id=song_id
        )

        try:
            if version == 1:
                audio_content = await self._fetch_audio_stream(
                    craft_my_song.streaming_url
                )
            else:
                audio_content = await self._fetch_audio_stream(
                    craft_my_song.streaming_url_v2
                )

            return StreamingResponse(
                io.BytesIO(audio_content),
                media_type="audio/mpeg",
                headers={
                    "Content-Disposition": f'attachment; filename="{craft_my_song.title}.mp3"',
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                    "Expires": "0",
                },
            )
        except Exception as e:
            logger.error(f"Error downloading song {song_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error downloading the song",
            )

    async def get_generated_track_by_id(self, song_id: str) -> IAHCraftMySong:
        query = select(IAHCraftMySong).where(IAHCraftMySong.id == song_id)
        record = await self.session.execute(query)

        craft_my_song = record.scalar_one_or_none()

        if craft_my_song is None:
            raise HTTPException(
                detail="Sorry, the song you requested isn't available",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # get the user object for song user
        user_query = select(User).where(User.id == craft_my_song.user_id)
        user_result = await self.session.execute(user_query)
        user = user_result.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                detail="User not found", status_code=status.HTTP_404_NOT_FOUND
            )

        return {
            "song_details": craft_my_song,
            "user_details": user,
        }
