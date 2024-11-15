import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiofiles
from fastapi import Depends, HTTPException, UploadFile, status
from PIL import Image
from pydantic import UUID4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.track.audio_analyzer import AudioAnalyzerService
from app.common.s3_file_upload import S3FileClient
from app.config import settings
from app.database import db_session
from app.logger.logger import logger
from app.models import Track
from app.schemas import CreateTrack


class BulkTrackUploadService:
    CHUNK_SIZE = 1024 * 1024  # 1MB chunks

    def __init__(self, session: AsyncSession = Depends(db_session)) -> None:
        self.session = session
        self.s3_client = S3FileClient()
        logger.debug(
            f"BulkTrackUploadService initialized with chunk size: {self.CHUNK_SIZE}"
        )

    @staticmethod
    async def validate_files_basic(track_data: CreateTrack) -> bool:
        """Quick validation of file types"""
        logger.debug(f"Starting basic file validation for track: {track_data.name}")

        allowed_audio = {"audio/mpeg", "audio/wav"}
        allowed_image = {"image/jpeg", "image/png"}

        # Log file types
        logger.debug(
            f"Instrumental audio type: {track_data.instrumental_audio_file.content_type}"
        )
        logger.debug(f"Hires audio type: {track_data.hires_audio_file.content_type}")
        logger.debug(f"Cover image type: {track_data.cover_image_file.content_type}")

        # Required files validation
        if (
            track_data.instrumental_audio_file.content_type not in allowed_audio
            or track_data.hires_audio_file.content_type not in allowed_audio
            or track_data.cover_image_file.content_type not in allowed_image
        ):
            logger.warning(f"Invalid file type detected for track: {track_data.name}")
            return False

        # Optional files validation
        if track_data.upright_audio_file:
            logger.debug(
                f"Upright audio type: {track_data.upright_audio_file.content_type}"
            )
            if track_data.upright_audio_file.content_type not in allowed_audio:
                logger.warning(
                    f"Invalid upright audio file type for track: {track_data.name}"
                )
                return False

        if track_data.reverse_audio_file:
            logger.debug(
                f"Reverse audio type: {track_data.reverse_audio_file.content_type}"
            )
            if track_data.reverse_audio_file.content_type not in allowed_audio:
                logger.warning(
                    f"Invalid reverse audio file type for track: {track_data.name}"
                )
                return False

        logger.debug(f"File validation successful for track: {track_data.name}")
        return True

    async def create_initial_track(self, **kwargs) -> Track:
        """Create initial track record with minimal data"""
        logger.debug(f"Creating initial track record with name: {kwargs.get('name')}")
        try:
            track = Track(**kwargs)
            self.session.add(track)
            await self.session.commit()
            await self.session.refresh(track)
            logger.debug(
                f"Initial track record created successfully with ID: {track.id}"
            )
            return track
        except Exception as e:
            logger.error(f"Error creating initial track record: {str(e)}")
            raise

    async def process_track_files(self, track_id: UUID4, track_data: CreateTrack):
        """Process track files in background"""
        try:
            # Update track status
            track = await self.get_track_by_id(track_id)
            track.status = "processing_files"
            await self.session.commit()
            logger.debug(f"Track status updated to processing_files for ID: {track_id}")

            with tempfile.TemporaryDirectory() as temp_dir:
                logger.debug(f"Created temporary directory: {temp_dir}")
                temp_path = Path(temp_dir)

                # Process required files
                logger.debug("Processing required files")
                tasks = [
                    self._process_audio_file(
                        track_data.instrumental_audio_file, temp_path, "instrumental"
                    ),
                    self._process_audio_file(
                        track_data.hires_audio_file, temp_path, "hires"
                    ),
                    self._process_image_file(track_data.cover_image_file, temp_path),
                ]

                # Optional files
                if track_data.upright_audio_file:
                    logger.debug("Processing upright audio file")
                    tasks.append(
                        self._process_audio_file(
                            track_data.upright_audio_file, temp_path, "upright"
                        )
                    )
                if track_data.reverse_audio_file:
                    logger.debug("Processing reverse audio file")
                    tasks.append(
                        self._process_audio_file(
                            track_data.reverse_audio_file, temp_path, "reverse"
                        )
                    )

                # Process all files concurrently
                logger.debug("Starting concurrent file processing")
                processed_files = await asyncio.gather(*tasks)
                logger.debug(f"Completed processing {len(processed_files)} files")

                # Extract audio metadata
                logger.debug("Starting audio analysis")
                audio_analyzer = AudioAnalyzerService()

                # Use the stored content from processed files
                instrumental_file = next(
                    f for f in processed_files if f["type"] == "instrumental"
                )
                track_technical_data = await audio_analyzer.analyze(
                    file_content=instrumental_file["content"],
                    file_name=track_data.instrumental_audio_file.filename,
                )
                logger.debug("Completed audio analysis")

                # Upload files to S3
                logger.debug("Preparing S3 uploads")
                s3_tasks = []
                for file_info in processed_files:
                    if file_info:
                        s3_tasks.extend(
                            [
                                self._upload_to_s3(
                                    file_path=file_info["path"],
                                    folder_name=f"tracks/{track_data.name}",
                                    file_type=file_info["type"],
                                )
                            ]
                        )
                        if "thumbnail_path" in file_info:
                            s3_tasks.append(
                                self._upload_to_s3(
                                    file_path=file_info["thumbnail_path"],
                                    folder_name=f"tracks/{track_data.name}",
                                    file_type="thumbnail",
                                )
                            )

                logger.debug(f"Starting {len(s3_tasks)} S3 uploads")
                urls = await asyncio.gather(*s3_tasks)
                logger.debug("Completed S3 uploads")

                # Update track record
                await self._update_track_record(
                    track_id=track_id, urls=urls, technical_data=track_technical_data
                )
                logger.debug(
                    f"Successfully completed processing for track ID: {track_id}"
                )

        except Exception as e:
            logger.error(f"Error processing track files: {str(e)}")
            await self._mark_track_failed(track_id, str(e))
            raise

    async def _process_audio_file(
        self, file: UploadFile, temp_dir: Path, file_type: str
    ) -> Dict:
        """Process audio file in chunks and return content"""
        logger.debug(f"Processing {file_type} audio file: {file.filename}")
        file_path = temp_dir / f"{file_type}_{file.filename}"
        file_content = b""  # Initialize bytes string

        try:
            async with aiofiles.open(file_path, "wb") as f:
                total_size = 0
                while chunk := await file.read(self.CHUNK_SIZE):
                    await f.write(chunk)
                    file_content += chunk  # Store the content
                    total_size += len(chunk)
                logger.debug(f"Processed {total_size} bytes for {file_type} file")

            return {
                "path": file_path,
                "type": file_type,
                "content_type": file.content_type,
                "content": file_content,  # Include the content in return
            }
        except Exception as e:
            logger.error(f"Error processing {file_type} audio file: {str(e)}")
            raise

    async def _process_image_file(self, file: UploadFile, temp_dir: Path) -> Dict:
        """Process image and create thumbnail"""
        logger.debug(f"Processing image file: {file.filename}")
        original_path = temp_dir / f"original_{file.filename}"
        thumb_path = temp_dir / f"thumb_{file.filename}"

        try:
            # Save original
            async with aiofiles.open(original_path, "wb") as f:
                total_size = 0
                while chunk := await file.read(self.CHUNK_SIZE):
                    await f.write(chunk)
                    total_size += len(chunk)
                logger.debug(f"Processed {total_size} bytes for original image")

            # Create thumbnail
            await self._create_thumbnail(original_path, thumb_path)
            logger.debug("Created thumbnail successfully")

            return {
                "path": original_path,
                "thumbnail_path": thumb_path,
                "type": "cover",
                "content_type": file.content_type,
            }
        except Exception as e:
            logger.error(f"Error processing image file: {str(e)}")
            raise

    async def _create_thumbnail(self, source_path: Path, target_path: Path):
        """Create thumbnail asynchronously"""
        logger.debug(f"Creating thumbnail for: {source_path}")
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, self._create_thumbnail_sync, source_path, target_path
            )
            logger.debug(f"Thumbnail created at: {target_path}")
        except Exception as e:
            logger.error(f"Error creating thumbnail: {str(e)}")
            raise

    def _create_thumbnail_sync(self, source_path: Path, target_path: Path):
        """Synchronous thumbnail creation"""
        with Image.open(source_path) as img:
            img.thumbnail((settings.THUMBNAIL_WIDTH, settings.THUMBNAIL_HEIGHT))
            img.save(target_path)

    async def _upload_to_s3(
        self, file_path: Path, folder_name: str, file_type: str
    ) -> Tuple[str, str]:
        """Upload file to S3 and return URL with type"""
        logger.debug(f"Uploading {file_type} file to S3: {file_path}")
        try:
            async with aiofiles.open(file_path, "rb") as f:
                content = await f.read()

            url = self.s3_client.upload_file_if_not_exists(
                folder_name=folder_name,
                file_name=file_path.name,
                file_content=content,
                content_type=f"application/octet-stream",
            )
            logger.debug(f"Successfully uploaded {file_type} to S3: {url}")
            return (url, file_type)
        except Exception as e:
            logger.error(f"Error uploading to S3: {str(e)}")
            raise

    async def _update_track_record(
        self, track_id: UUID4, urls: List[Tuple[str, str]], technical_data: dict
    ):
        """Update track record with file URLs and technical data"""
        logger.debug(f"Updating track record for ID: {track_id}")

        try:
            # Convert technical_data to JSON string
            technical_data_json = json.dumps(technical_data)

            # Get the track
            track = await self.get_track_by_id(track_id)

            # Update URLs
            url_mapping = {
                "instrumental": "instrumental_audio_url",
                "hires": "hires_audio_url",
                "cover": "cover_image",
                "thumbnail": "thumbnail_image",
                "upright": "upright_audio_url",
                "reverse": "reverse_audio_url",
            }

            for url, file_type in urls:
                if field_name := url_mapping.get(file_type):
                    setattr(track, field_name, url)
                    logger.debug(f"Updated {field_name} with URL: {url}")

            # Update technical data and status
            track.track_technical_data = technical_data_json
            track.status = "completed"

            # Save changes
            self.session.add(track)
            await self.session.commit()

            logger.debug(f"Successfully updated track record for ID: {track_id}")

        except Exception as e:
            logger.error(f"Error updating track record: {str(e)}", exc_info=True)
            await self.session.rollback()
            raise

    async def _mark_track_failed(self, track_id: UUID4, error_message: str):
        """Mark track as failed"""
        logger.debug(f"Marking track as failed for ID: {track_id}")
        try:
            track = await self.get_track_by_id(track_id)
            track.status = "failed"
            track.error_message = error_message

            self.session.add(track)
            await self.session.commit()

            logger.debug(f"Track marked as failed with error: {error_message}")

        except Exception as e:
            logger.error(f"Error marking track as failed: {str(e)}")
            await self.session.rollback()
            raise

    async def get_track_by_id(self, track_id: UUID4) -> Track:
        """Get track by ID"""
        logger.debug(f"Fetching track with ID: {track_id}")
        try:
            result = await self.session.execute(
                select(Track).where(Track.id == track_id)
            )
            track = result.scalar_one_or_none()

            if not track:
                logger.warning(f"Track not found with ID: {track_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Track not found"
                )

            logger.debug(f"Successfully fetched track with ID: {track_id}")
            return track

        except Exception as e:
            logger.error(f"Error fetching track: {str(e)}")
            raise
