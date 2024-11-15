import asyncio
import json
import logging
import os
from typing import List

from fastapi import BackgroundTasks, Depends
from langchain.prompts import load_prompt
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import db_session
from app.logger.logger import logger
from app.models import Collection, CollectionEmbedding, Track, TrackEmbedding


class IngressService:
    def __init__(self, session: AsyncSession = Depends(db_session)) -> None:
        self.session = session
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
        )

    def _load_prompt_from_file_path(self, file_path: str):
        script_path = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_path)
        target_file_path = os.path.join(script_dir, file_path)
        return load_prompt(target_file_path)

    async def index_tracks_to_pgvector_database(self):
        track_records = await self.session.execute(
            select(Track).where(Track.ai_metadata != None)
        )
        tracks: List[Track] = track_records.scalars().fetchall()

        logger.debug(f"Found tracks {len(tracks)} for indexing")

        # Initialize OpenAI Embeddings
        embeddings = OpenAIEmbeddings()

        processed_count = 0

        for track in tracks:
            track_details = {
                "name": track.name,
                "id": str(track.id),
                "collection_id": str(track.collection_id),
                "description": track.description,
                "short_description": track.short_description,
                "upright_message": track.upright_message,
                "reverse_message": track.reverse_message,
                "frequency": track.frequency,
                "frequency_meaning": track.frequency_meaning,
                "metadata": track.ai_metadata,
            }

            content = json.dumps(track_details)
            # Generate embedding
            embedding_vector = embeddings.embed_query(content)

            # Check if embedding already exists for this track
            existing_embedding = await self.session.execute(
                select(TrackEmbedding).where(TrackEmbedding.track_id == track.id)
            )
            existing_embedding = existing_embedding.scalar_one_or_none()

            if existing_embedding:
                # Update existing embedding
                existing_embedding.embedding = embedding_vector
                existing_embedding.embedding_metadata = track_details
                existing_embedding.collection_id = track.collection_id
                action = "updated"
            else:
                # Create new embedding
                track_embedding = TrackEmbedding(
                    track_id=track.id,
                    collection_id=track.collection_id,
                    embedding=embedding_vector,
                    embedding_metadata=track_details,
                )
                self.session.add(track_embedding)
                action = "created"

            try:
                # update the track details index column
                track.is_index = True
                await self.session.commit()
                processed_count += 1
                logger.info(
                    f"Track ID {str(track.id)} has been {action} in the vector database"
                )
            except Exception as e:
                await self.session.rollback()
                logger.error(
                    f"Error {action} Track ID {str(track.id)} in vector database: {str(e)}"
                )
                raise

        return processed_count

    async def index_collections_to_pgvector_database(self):
        WHEEL_OF_FORTUNE = "cd708d0a-42ae-4336-9063-093f5fef4d6d"
        collection_ids_to_ignore = [WHEEL_OF_FORTUNE]

        # Get all active collections except ignored ones
        collection_records = await self.session.execute(
            select(Collection)
            .where(Collection.id.notin_(collection_ids_to_ignore))
            .where(Collection.is_active == True)
            .where(Collection.is_hidden != True)
            .where(Collection.is_private != True)
        )
        collections: List[Collection] = collection_records.scalars().fetchall()

        embeddings = OpenAIEmbeddings()

        for collection in collections:
            # Prepare collection data for embedding
            filtered_collection_data = {
                "name": collection.name,
                "lead_producer": collection.lead_producer,
                "description": collection.description,
                "tempo": collection.tempo,
                "short_description": collection.short_description,
                "id": str(collection.id),
                "audience": collection.audience,
                "genre": collection.genre,
                "chakra": collection.chakra,
                "frequency": collection.frequency,
            }
            content = json.dumps(filtered_collection_data)

            # Generate new embedding
            embedding_vector = embeddings.embed_query(content)

            # Check if embedding already exists for this collection
            existing_embedding = await self.session.execute(
                select(CollectionEmbedding).where(
                    CollectionEmbedding.collection_id == collection.id
                )
            )
            existing_embedding = existing_embedding.scalar_one_or_none()

            if existing_embedding:
                # Update existing embedding
                existing_embedding.embedding = embedding_vector
                existing_embedding.embedding_metadata = filtered_collection_data
                logger.info(
                    f"Updated existing embedding for Collection ID {str(collection.id)}"
                )
            else:
                # Create new embedding
                track_embedding = CollectionEmbedding(
                    collection_id=collection.id,
                    embedding=embedding_vector,
                    embedding_metadata=filtered_collection_data,
                )
                self.session.add(track_embedding)
                logger.info(
                    f"Created new embedding for Collection ID {str(collection.id)}"
                )

            collection.is_index = True
            await self.session.commit()

        return len(collections)

    async def generate_ai_summary_for_all_tracks(
        self, background_tasks: BackgroundTasks
    ):

        track_records = await self.session.execute(select(Track))
        tracks = track_records.scalars().fetchall()

        logger.debug(
            f"TRACK SUMMARY: found {len(tracks)} tracks to generate summary for"
        )

        track_data = []
        for track in tracks:
            collection_record = await self.session.execute(
                select(Collection).where(Collection.id == track.collection_id)
            )
            collection = collection_record.scalars().first()
            track_data.append(
                {
                    "audio_track_details": track,
                    "track_collection_details": (
                        collection
                        if collection
                        else "No collection found for this track"
                    ),
                }
            )
        background_tasks.add_task(
            self._process_track_summary_generation_n_background,
            track_data,
            background_tasks,
        )

    async def _process_track_summary_generation_n_background(
        self, track_data: dict, background_tasks: BackgroundTasks
    ) -> None:
        for i, track in enumerate(track_data):
            background_tasks.add_task(self._generate_track_summary_from_ai, track, i)
            # add wait for every 10 tracks
            if i % 10 == 0:
                await asyncio.sleep(1)

    async def _generate_track_summary_from_ai(
        self, track_data: dict, index: int
    ) -> None:
        try:
            output_parser = StrOutputParser()
            llm = ChatOpenAI(
                openai_api_key=settings.OPENAI_API_KEY,
                model="gpt-4o-mini",
                temperature=0.3,
            )

            prompt = self._load_prompt_from_file_path(
                "prompts/generate_track_summary_optimized.yaml"
            )
            chain = prompt | llm | output_parser

            output = chain.invoke({"context": track_data})
            logger.debug(
                f"Processed task: {index} - track id: {track_data['audio_track_details'].id}"
            )
            # update the database with the AI metadata
            track_record = await self.session.execute(
                select(Track).where(Track.id == track_data["audio_track_details"].id)
            )
            track = track_record.scalars().first()
            track.ai_metadata = output
            await self.session.commit()
            logger.debug(
                f"Updated track: {track_data['audio_track_details'].id} with AI metadata"
            )

            return {"ai_metadata": output, "track": track_data}
        except Exception as e:
            logger.error(
                f"Error processing task: {index} - track id: {track_data['audio_track_details'].id}"
            )
            logger.error(f"Error: {e}")
            return {"ai_metadata": None, "track": track_data}

    async def generate_ai_summary_as_batch(self):

        track_records = await self.session.execute(select(Track))
        tracks = track_records.scalars().fetchall()

        logger.debug(
            f"TRACK SUMMARY: found {len(tracks)} tracks to generate summary for"
        )

        track_data = []
        for track in tracks:
            collection_record = await self.session.execute(
                select(Collection).where(Collection.id == track.collection_id)
            )
            collection = collection_record.scalars().first()
            track_data.append(
                {
                    "audio_track_details": track,
                    "track_collection_details": (
                        collection
                        if collection
                        else "No collection found for this track"
                    ),
                }
            )

        for i, track in enumerate(track_data):
            await self._generate_track_summary_from_ai(track, i)
            # add wait for every 10 tracks
            if i % 10 == 0:
                await asyncio.sleep(1)

    async def generate_ai_summary_for_missing_tracks(self):

        track_records = await self.session.execute(
            select(Track).where(Track.ai_metadata == None)
        )
        tracks = track_records.scalars().fetchall()

        logger.debug(
            f"TRACK SUMMARY: found {len(tracks)} metadata details missing tracks"
        )

        track_data = []
        for track in tracks:
            collection_record = await self.session.execute(
                select(Collection).where(Collection.id == track.collection_id)
            )
            collection = collection_record.scalars().first()
            track_data.append(
                {
                    "audio_track_details": track,
                    "track_collection_details": (
                        collection
                        if collection
                        else "No collection found for this track"
                    ),
                }
            )

        for i, track in enumerate(track_data):
            await self._generate_track_summary_from_ai(track, i)
            if i % 20 == 0:
                await asyncio.sleep(1)

    async def _update_collection_index(self):
        WHEEL_OF_FORTUNE = "cd708d0a-42ae-4336-9063-093f5fef4d6d"
        collection_ids_to_ignore = [WHEEL_OF_FORTUNE]

        # Get all active collections except ignored ones
        collection_records = await self.session.execute(
            select(Collection)
            .where(Collection.id.notin_(collection_ids_to_ignore))
            .where(Collection.is_active == True)
            .where(Collection.is_hidden != True)
            .where(Collection.is_private != True)
            .where(Collection.is_index == False)
        )
        collections: List[Collection] = collection_records.scalars().fetchall()

        embeddings = OpenAIEmbeddings()

        for collection in collections:
            # Prepare collection data for embedding
            filtered_collection_data = {
                "name": collection.name,
                "lead_producer": collection.lead_producer,
                "description": collection.description,
                "tempo": collection.tempo,
                "short_description": collection.short_description,
                "id": str(collection.id),
                "audience": collection.audience,
                "genre": collection.genre,
                "chakra": collection.chakra,
                "frequency": collection.frequency,
            }
            content = json.dumps(filtered_collection_data)

            # Generate new embedding
            embedding_vector = embeddings.embed_query(content)

            # Check if embedding already exists for this collection
            existing_embedding = await self.session.execute(
                select(CollectionEmbedding).where(
                    CollectionEmbedding.collection_id == collection.id
                )
            )
            existing_embedding = existing_embedding.scalar_one_or_none()

            if existing_embedding:
                # Update existing embedding
                existing_embedding.embedding = embedding_vector
                existing_embedding.embedding_metadata = filtered_collection_data
                logger.info(
                    f"Updated existing embedding for Collection ID {str(collection.id)}"
                )
            else:
                # Create new embedding
                track_embedding = CollectionEmbedding(
                    collection_id=collection.id,
                    embedding=embedding_vector,
                    embedding_metadata=filtered_collection_data,
                )
                self.session.add(track_embedding)
                logger.info(
                    f"Created new embedding for Collection ID {str(collection.id)}"
                )

            collection.is_index = True
            await self.session.commit()

        return len(collections)

    async def _update_track_index(self):
        track_records = await self.session.execute(
            select(Track)
            .where(Track.ai_metadata != None)
            .where(Track.is_index == False)
        )
        tracks: List[Track] = track_records.scalars().fetchall()

        logger.debug(f"Found {len(tracks)} for indexing")

        # Initialize OpenAI Embeddings
        embeddings = OpenAIEmbeddings()

        processed_count = 0

        for track in tracks:
            track_details = {
                "name": track.name,
                "id": str(track.id),
                "collection_id": str(track.collection_id),
                "description": track.description,
                "short_description": track.short_description,
                "upright_message": track.upright_message,
                "reverse_message": track.reverse_message,
                "frequency": track.frequency,
                "frequency_meaning": track.frequency_meaning,
                "metadata": track.ai_metadata,
            }

            content = json.dumps(track_details)
            # Generate embedding
            embedding_vector = embeddings.embed_query(content)

            # Check if embedding already exists for this track
            existing_embedding = await self.session.execute(
                select(TrackEmbedding).where(TrackEmbedding.track_id == track.id)
            )
            existing_embedding = existing_embedding.scalar_one_or_none()

            if existing_embedding:
                # Update existing embedding
                existing_embedding.embedding = embedding_vector
                existing_embedding.embedding_metadata = track_details
                existing_embedding.collection_id = track.collection_id
                action = "updated"
            else:
                # Create new embedding
                track_embedding = TrackEmbedding(
                    track_id=track.id,
                    collection_id=track.collection_id,
                    embedding=embedding_vector,
                    embedding_metadata=track_details,
                )
                self.session.add(track_embedding)
                action = "created"

            try:
                # update the track details index column
                track.is_index = True
                await self.session.commit()
                processed_count += 1
                logger.info(
                    f"Track ID {str(track.id)} has been {action} in the vector database"
                )
            except Exception as e:
                await self.session.rollback()
                logger.error(
                    f"Error {action} Track ID {str(track.id)} in vector database: {str(e)}"
                )
                raise

        return processed_count

    async def _remove_indexes_on_collections_and_tracks_based_on_visibility(self):
        hidden_collections_record = await self.session.execute(
            select(Collection).where(
                or_(Collection.is_hidden == True, Collection.is_private == True)
            )
        )

        hidden_collections: List[Collection] = (
            hidden_collections_record.scalars().fetchall()
        )

        logger.debug(
            f"Hidden {len(hidden_collections)} collections found removing from index"
        )

        hidden_collection_ids = [collection.id for collection in hidden_collections]

        hidden_tracks_records = await self.session.execute(
            select(Track).where(Track.collection_id.in_(hidden_collection_ids))
        )

        hidden_tracks = hidden_tracks_records.scalars().fetchall()
        logger.debug(f"Hidden {len(hidden_tracks)} tracks found removing from index")

        hidden_track_ids = [track.id for track in hidden_tracks]

        # removing index from collection index table and track index table
        # Remove collection embeddings
        await self.session.execute(
            delete(CollectionEmbedding).where(
                CollectionEmbedding.collection_id.in_(hidden_collection_ids)
            )
        )

        # Remove track embeddings
        await self.session.execute(
            delete(TrackEmbedding).where(TrackEmbedding.track_id.in_(hidden_track_ids))
        )

        # Update is_index to False for collections
        await self.session.execute(
            update(Collection)
            .where(Collection.id.in_(hidden_collection_ids))
            .values(is_index=False)
        )

        # Update is_index to False for tracks
        await self.session.execute(
            update(Track).where(Track.id.in_(hidden_track_ids)).values(is_index=False)
        )

        await self.session.commit()

    async def update_vector_indexes(self):
        # first generate ai metadata for all the missing tracks
        track_records = await self.session.execute(
            select(Track).where(Track.ai_metadata == None)
        )
        tracks = track_records.scalars().fetchall()

        logger.debug(
            f"Found {len(tracks)} without AI metadata begins generating metadata now"
        )

        track_data = []
        for track in tracks:
            collection_record = await self.session.execute(
                select(Collection).where(Collection.id == track.collection_id)
            )
            collection = collection_record.scalars().first()
            track_data.append(
                {
                    "audio_track_details": track,
                    "track_collection_details": (
                        collection
                        if collection
                        else "No collection found for this track"
                    ),
                }
            )

        for i, track in enumerate(track_data):
            await self._generate_track_summary_from_ai(track, i)
            # add wait for every 10 tracks
            if i % 10 == 0:
                await asyncio.sleep(1)

        logger.debug("AI metadata generation completed indexing new collections first")

        # get the collection which is not indexed
        updated_collections = await self._update_collection_index()

        logger.debug(f"Collections {updated_collections} has been newly indexed")

        logger.debug("Start Track data indexing for missing indexes")

        updated_tracks = await self._update_track_index()

        logger.debug(f"Tracks {updated_tracks} has been newly indexed")

        # now check for visibility hidden collections and tracks and remove then from the vector indexes if exists
        logger.debug("Started checking visibility and remove index based on visibility")
        await self._remove_indexes_on_collections_and_tracks_based_on_visibility()

    async def get_vector_data_index_status(self):
        # Get total track count
        total_tracks = await self.session.execute(select(func.count(Track.id)))
        total_track_count = total_tracks.scalar()

        # Get count of indexed tracks
        indexed_tracks = await self.session.execute(
            select(func.count(TrackEmbedding.id))
        )
        indexed_track_count = indexed_tracks.scalar()

        # Get count of hidden or private tracks
        hidden_or_private_tracks = await self.session.execute(
            select(func.count(Track.id)).where(
                or_(Track.is_hidden == True, Track.is_private == True)
            )
        )
        hidden_or_private_track_count = hidden_or_private_tracks.scalar()

        # Get total collection count
        total_collections = await self.session.execute(
            select(func.count(Collection.id))
        )
        total_collection_count = total_collections.scalar()

        # Get count of indexed collections
        indexed_collections = await self.session.execute(
            select(func.count(CollectionEmbedding.id))
        )
        indexed_collection_count = indexed_collections.scalar()

        # Get count of hidden or private collections
        hidden_or_private_collections = await self.session.execute(
            select(func.count(Collection.id)).where(
                or_(Collection.is_hidden == True, Collection.is_private == True)
            )
        )
        hidden_or_private_collection_count = hidden_or_private_collections.scalar()

        return {
            "total_tracks": total_track_count,
            "indexed_tracks": indexed_track_count,
            "private_tracks": hidden_or_private_track_count,
            "total_collections": total_collection_count,
            "indexed_collection": indexed_collection_count,
            "private_collection": hidden_or_private_collection_count,
        }

    async def get_vector_db_sync_status(self):
        # Step 1: Get all collection IDs where `is_hidden` or `is_private` is True
        hidden_or_private_collections_result = await self.session.execute(
            select(Collection.id).where(
                or_(Collection.is_hidden == True, Collection.is_private == True)
            )
        )
        hidden_or_private_collection_ids = {
            str(row[0]) for row in hidden_or_private_collections_result.fetchall()
        }

        # Step 2: Get all track IDs and their collection IDs from the Track table
        track_ids_result = await self.session.execute(
            select(Track.id, Track.collection_id, Track.is_hidden, Track.is_private)
        )
        track_data = track_ids_result.fetchall()

        # Separate tracks into visible and hidden/private
        all_visible_track_ids = set()  # Tracks that are valid and visible
        hidden_or_private_track_ids = set()  # Tracks that are hidden or private

        for track_id, collection_id, is_hidden, is_private in track_data:
            if (is_hidden or is_private) or str(
                collection_id
            ) in hidden_or_private_collection_ids:
                hidden_or_private_track_ids.add(str(track_id))
            else:
                all_visible_track_ids.add(str(track_id))

        # Step 3: Get all track IDs from the TrackEmbedding table
        embedding_ids_result = await self.session.execute(
            select(TrackEmbedding.track_id)
        )
        embedding_ids = {str(row[0]) for row in embedding_ids_result.fetchall()}

        # Step 4: Identify overfitted and missing track IDs
        # Overfitted tracks: Tracks in embedding table but not valid in Track table
        overfitted_track_ids = embedding_ids - all_visible_track_ids

        # Missing tracks: Tracks in Track table but not in embedding table
        missing_track_ids = all_visible_track_ids - embedding_ids

        # Step 5: Log the results
        logger.debug(f"Missing track IDs to index: {len(missing_track_ids)}")
        logger.debug(f"Overfitted track IDs to remove: {len(overfitted_track_ids)}")

        # Step 6: Return the result
        return {
            "missing_track_ids": list(missing_track_ids),  # Tracks that need indexing
            "overfitted_track_ids": list(
                overfitted_track_ids
            ),  # Tracks that need removal
            "total_tracks": len(all_visible_track_ids),
            "total_embeddings": len(embedding_ids),
        }

    async def resync_track_vector_indexes(self):
        # Step 1: Get hidden or private collections
        hidden_or_private_collections_result = await self.session.execute(
            select(Collection.id).where(
                or_(Collection.is_hidden == True, Collection.is_private == True)
            )
        )
        hidden_or_private_collection_ids = {
            str(row[0]) for row in hidden_or_private_collections_result.fetchall()
        }

        # Step 2: Get all track IDs with their collections
        track_ids_result = await self.session.execute(
            select(Track.id, Track.collection_id)
        )
        track_ids_with_collections = track_ids_result.fetchall()

        # Filter tracks based on collections
        all_track_ids = set()
        tracks_to_remove = set()
        for track_id, collection_id in track_ids_with_collections:
            if str(collection_id) in hidden_or_private_collection_ids:
                tracks_to_remove.add(str(track_id))
            else:
                all_track_ids.add(str(track_id))

        # Step 3: Get all track IDs from the embedding table
        embedding_ids_result = await self.session.execute(
            select(TrackEmbedding.track_id)
        )
        embedding_ids = {str(row[0]) for row in embedding_ids_result.fetchall()}

        # Step 4: Identify missing and overfitted track IDs
        missing_track_ids = all_track_ids - embedding_ids
        overfitted_track_ids = embedding_ids - all_track_ids

        # Exclude tracks to remove from missing IDs
        missing_track_ids -= tracks_to_remove

        # Include tracks to remove in overfitted IDs
        overfitted_track_ids.update(tracks_to_remove)

        # Step 5: Remove overfitted track IDs from the embedding table
        if overfitted_track_ids:
            await self.session.execute(
                delete(TrackEmbedding).where(
                    TrackEmbedding.track_id.in_(overfitted_track_ids)
                )
            )
            await self.session.commit()
            logger.info(
                f"Removed {len(overfitted_track_ids)} overfitted tracks from embedding table"
            )

        # Step 6: Process missing track IDs for indexing
        for track_id in missing_track_ids:
            # Check if AI metadata exists for the track
            track_record = await self.session.execute(
                select(Track).where(Track.id == track_id)
            )
            track = track_record.scalars().first()

            if not track.ai_metadata:
                # Generate AI summary for the track
                await self._generate_track_summary_from_ai(
                    {"audio_track_details": track}, 0
                )
                logger.info(f"Generated AI metadata for track ID {track_id}")

            # Prepare track details for embedding
            track_details = {
                "name": track.name,
                "id": str(track.id),
                "collection_id": str(track.collection_id),
                "description": track.description,
                "short_description": track.short_description,
                "upright_message": track.upright_message,
                "reverse_message": track.reverse_message,
                "frequency": track.frequency,
                "frequency_meaning": track.frequency_meaning,
                "metadata": track.ai_metadata,
            }
            content = json.dumps(track_details)

            # Generate embedding vector
            embeddings = OpenAIEmbeddings()
            embedding_vector = embeddings.embed_query(content)

            # Create new embedding entry
            track_embedding = TrackEmbedding(
                track_id=track.id,
                collection_id=track.collection_id,
                embedding=embedding_vector,
                embedding_metadata=track_details,
            )
            self.session.add(track_embedding)

        # Commit the new embeddings
        await self.session.commit()
        logger.info(
            f"Indexed {len(missing_track_ids)} new tracks into the embedding table"
        )

        # Return a summary
        return {
            "missing_track_ids": list(missing_track_ids),
            "overfitted_track_ids": list(overfitted_track_ids),
            "total_tracks": len(all_track_ids),
            "total_embeddings": len(embedding_ids),
        }

    async def resync_collection_vector_indexes(self):
        WHEEL_OF_FORTUNE = (
            "cd708d0a-42ae-4336-9063-093f5fef4d6d"  # Collection ID to exclude
        )
        # Step 1: Get hidden or private collections
        hidden_or_private_collections_result = await self.session.execute(
            select(Collection.id).where(
                or_(Collection.is_hidden == True, Collection.is_private == True)
            )
        )
        hidden_or_private_collection_ids = {
            str(row[0]) for row in hidden_or_private_collections_result.fetchall()
        }

        # Step 2: Get all collection IDs from the Collection table
        collection_ids_result = await self.session.execute(
            select(Collection.id, Collection.is_hidden, Collection.is_private)
        )
        collection_data = collection_ids_result.fetchall()

        # Separate collections into visible and hidden/private
        all_visible_collection_ids = set()  # Collections that are valid and visible
        hidden_or_private_collections = set()  # Collections that are hidden or private

        for collection_id, is_hidden, is_private in collection_data:
            if (
                is_hidden or is_private or str(collection_id) == WHEEL_OF_FORTUNE
            ):  # Exclude WHEEL_OF_FORTUNE
                hidden_or_private_collections.add(str(collection_id))
            else:
                all_visible_collection_ids.add(str(collection_id))

        # Step 3: Get all collection IDs from the CollectionEmbedding table
        embedding_collection_ids_result = await self.session.execute(
            select(CollectionEmbedding.collection_id)
        )
        embedding_collection_ids = {
            str(row[0]) for row in embedding_collection_ids_result.fetchall()
        }

        # Step 4: Identify missing and overfitted collection IDs
        # Overfitted collections: In embedding table but not valid in Collection table
        overfitted_collection_ids = (
            embedding_collection_ids - all_visible_collection_ids
        )

        # Include hidden or private collections in the overfitted list
        overfitted_collection_ids.update(hidden_or_private_collections)

        # Missing collections: In Collection table but not in embedding table
        missing_collection_ids = all_visible_collection_ids - embedding_collection_ids

        # Step 5: Remove overfitted collection IDs from the embedding table
        if overfitted_collection_ids:
            await self.session.execute(
                delete(CollectionEmbedding).where(
                    CollectionEmbedding.collection_id.in_(overfitted_collection_ids)
                )
            )
            await self.session.commit()
            logger.info(
                f"Removed {len(overfitted_collection_ids)} overfitted collections from embedding table"
            )

        # Step 6: Process missing collection IDs for indexing
        for collection_id in missing_collection_ids:
            # Fetch collection details
            collection_record = await self.session.execute(
                select(Collection).where(Collection.id == collection_id)
            )
            collection = collection_record.scalars().first()

            # Prepare collection details for embedding
            collection_details = {
                "name": collection.name,
                "lead_producer": collection.lead_producer,
                "description": collection.description,
                "tempo": collection.tempo,
                "short_description": collection.short_description,
                "id": str(collection.id),
                "audience": collection.audience,
                "genre": collection.genre,
                "chakra": collection.chakra,
                "frequency": collection.frequency,
            }
            content = json.dumps(collection_details)

            # Generate embedding vector
            embeddings = OpenAIEmbeddings()
            embedding_vector = embeddings.embed_query(content)

            # Create new embedding entry
            collection_embedding = CollectionEmbedding(
                collection_id=collection.id,
                embedding=embedding_vector,
                embedding_metadata=collection_details,
            )
            self.session.add(collection_embedding)

        # Commit the new embeddings
        await self.session.commit()
        logger.info(
            f"Indexed {len(missing_collection_ids)} new collections into the embedding table"
        )

        # Return a summary
        return {
            "missing_collection_ids": list(
                missing_collection_ids
            ),  # Collections to index
            "overfitted_collection_ids": list(
                overfitted_collection_ids
            ),  # Collections to remove
            "total_collections": len(all_visible_collection_ids),
            "total_collection_embeddings": len(embedding_collection_ids),
        }
