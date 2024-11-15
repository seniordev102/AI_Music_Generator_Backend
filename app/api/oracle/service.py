import asyncio
import json
import logging
import os
import random
import time
from io import BytesIO
from typing import List

import requests
from fastapi import BackgroundTasks, Depends
from langchain.chains import create_structured_output_runnable
from langchain.prompts import load_prompt
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAI as LangChainOpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from PIL import Image
from pinecone import Pinecone, ServerlessSpec
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.chat.service import ChatService
from app.api.user.service import UserService
from app.common.s3_file_upload import S3FileClient
from app.config import settings
from app.database import db_session
from app.models import (
    ChatHistory,
    Collection,
    CollectionEmbedding,
    Track,
    TrackEmbedding,
)
from app.schemas import APIUsage, CreateChatMessage, UpdateAPIUsage


class OracleService:
    def __init__(self, session: AsyncSession = Depends(db_session)) -> None:
        self.session = session
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
        )
        self.logger = logging.getLogger(__name__)

    async def get_all_collections(self) -> list[Collection]:

        # Fetch paginated items
        collection_list = await self.session.execute(
            select(Collection).order_by(Collection.order_seq.asc())
        )
        collections = collection_list.scalars().fetchall()
        return collections

    async def get_all_tracks(self) -> list[Track]:
        tracks_records = await self.session.execute(
            select(Track)
            .where(Track.instrumental_audio_url != None)
            .order_by(Track.order_seq.asc())
        )
        tracks = tracks_records.scalars().fetchall()
        return tracks

    async def get_all_data_for_indexing(self) -> dict:
        track_records = await self.session.execute(
            select(Track).where(Track.ai_metadata == None)
        )
        tracks = track_records.scalars().fetchall()

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
        return track_data

    async def sync_all_ai_metadata_for_tracks(
        self, background_tasks: BackgroundTasks
    ) -> None:
        track_records = await self.session.execute(
            select(Track).where(Track.ai_metadata == None)
        )
        tracks = track_records.scalars().fetchall()

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

        self.logger.info(
            f"Tasks started, processing in the background found: {len(track_data)} tracks."
        )

        # fist_ten = track_data[:150]
        # background_tasks.add_task(
        #     self.process_data_in_background, fist_ten, background_tasks)

        return f"Tasks started, processing in the background found: {len(track_data)} tracks."

    async def process_data_in_background(
        self, track_data: dict, background_tasks: BackgroundTasks
    ) -> None:
        for i, track in enumerate(track_data):
            background_tasks.add_task(self.process_track_data, track, i)
            # add wait for every 10 tracks
            if i % 10 == 0:
                await asyncio.sleep(1)

    async def process_track_data(self, track_data: dict, task_id: int) -> dict:
        try:
            output_parser = StrOutputParser()
            llm = ChatOpenAI(openai_api_key=settings.OPENAI_API_KEY)

            prompt = self.load_prompt_from_file_path(
                "prompts/track_ai_metadata_generator.yaml"
            )
            chain = prompt | llm | output_parser

            output = chain.invoke({"context": track_data})
            self.logger.info(
                f"Processed task: {task_id} - track id: {track_data['audio_track_details'].id}"
            )
            self.logger.info(f"AI Metadata: {output}")

            # update the database with the AI metadata
            track_record = await self.session.execute(
                select(Track).where(Track.id == track_data["audio_track_details"].id)
            )
            track = track_record.scalars().first()
            track.ai_metadata = output
            await self.session.commit()
            self.logger.info(
                f"Updated track: {track_data['audio_track_details'].id} with AI metadata"
            )

            return {"ai_metadata": output, "track": track_data}
        except Exception as e:
            self.logger.error(
                f"Error processing task: {task_id} - track id: {track_data['audio_track_details'].id}"
            )
            self.logger.error(f"Error: {e}")
            return {"ai_metadata": None, "track": track_data}

    async def generate_relevant_tracks(self, user_prompt: str) -> None:
        embeddings = OpenAIEmbeddings()
        index_name = "iah-tracks"
        vector_store = PineconeVectorStore.from_existing_index(
            index_name=index_name, embedding=embeddings
        )

        retriever = vector_store.as_retriever(search_kwargs={"k": 25})

        template = """Answer the question based only on the following context:
        always select most suitable 10 tracks i need exactly 10 tracks no more no less
        {context}
        Question: {question} and only give the 10 track ids as a list
        """
        prompt = ChatPromptTemplate.from_template(template)

        llm = ChatOpenAI(model_name="gpt-4-turbo-preview", temperature=0)

        track_id_schema = {
            "type": "function",
            "function": {
                "name": "get_track_ids",
                "description": "Return the list of track ids as a string array.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "track_ids": {
                            "description": "String array of track ids",
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["track_ids"],
                },
            },
        }

        structured_llm = create_structured_output_runnable(
            track_id_schema,
            llm,
            mode="openai-tools",
            enforce_function_usage=True,
            return_single=True,
        )
        chain = (
            RunnableParallel({"context": retriever, "question": RunnablePassthrough()})
            | prompt
            | structured_llm
        )

        # # Question
        response = chain.invoke(user_prompt)
        return response

    async def generate_album_art_based_on_prompt(self, user_prompt: str) -> None:
        llm = LangChainOpenAI(temperature=0.9)
        prompt = prompt = self.load_prompt_from_file_path(
            "prompts/image_generation_prompt.yaml"
        )
        chain = RunnableParallel({"image_desc": RunnablePassthrough()}) | prompt | llm
        image_url = DallEAPIWrapper(
            model="dall-e-3",
            size="1792x1024",
        ).run(chain.invoke(user_prompt))

        # download the image and upload into the s3 bucket
        s3Client = S3FileClient()

        # generate a file name using timestamp
        file_name = f"album_art_{int(time.time())}.png"
        image_url_s3 = await s3Client.upload_image_from_url(
            image_url, file_name, "image/png"
        )

        return {"image": image_url_s3}

    async def perform_similarity_search_form_user_prompt(
        self, user_prompt: str, k: int = 10
    ) -> List[str]:
        embeddings = OpenAIEmbeddings()
        index_name = "tracks"

        vector_store = PineconeVectorStore.from_existing_index(
            index_name=index_name, embedding=embeddings
        )

        print("Performing similarity search for user prompt", k)
        retriever = vector_store.as_retriever(search_kwargs={"k": 15})

        similarity_response = retriever.get_relevant_documents(user_prompt)

        track_data = []
        if similarity_response and len(similarity_response) > 0:
            for document in similarity_response:
                track_details = {
                    "track_id": document.metadata["track_id"],
                    "collection_id": document.metadata["collection_id"],
                }
                track_data.append(track_details)

        # Group tracks by collection ID
        tracks_by_collection = {}
        for track in track_data:
            collection_id = track["collection_id"]
            if collection_id not in tracks_by_collection:
                tracks_by_collection[collection_id] = []
            tracks_by_collection[collection_id].append(track["track_id"])

        # Initially select one track from as many different collections as possible
        selected_track_ids = []
        collections_represented = set()

        # Select one track from each collection if possible, to maximize diversity
        for collection_id, track_ids in tracks_by_collection.items():
            if len(selected_track_ids) < k:
                # Or select based on some criteria
                random_track_id = random.choice(track_ids)
                selected_track_ids.append(random_track_id)
                collections_represented.add(collection_id)
            else:
                break

        # Fill in with tracks from the original list, prioritizing collections not yet represented
        if len(selected_track_ids) < k:
            for collection_id, track_ids in tracks_by_collection.items():
                if collection_id not in collections_represented:
                    for track_id in track_ids:
                        if len(selected_track_ids) < k:
                            selected_track_ids.append(track_id)
                        else:
                            break
                if len(selected_track_ids) == k:
                    break

        # If still not enough, add more tracks from any collection
        while len(selected_track_ids) < k:
            for track_ids in tracks_by_collection.values():
                for track_id in track_ids:
                    if track_id not in selected_track_ids:
                        selected_track_ids.append(track_id)
                        if len(selected_track_ids) == k:
                            break
                if len(selected_track_ids) == k:
                    break

        return selected_track_ids[:k]

    async def generate_square_album_art_based_on_prompt(self, user_prompt: str) -> None:
        llm = LangChainOpenAI(temperature=0.9)
        prompt = self.load_prompt_from_file_path("prompts/image_generation_prompt.yaml")
        chain = RunnableParallel({"image_desc": RunnablePassthrough()}) | prompt | llm
        image_url = DallEAPIWrapper(
            model="dall-e-3",
            size="1024x1024",
        ).run(chain.invoke(user_prompt))

        # download the image and upload into the s3 bucket
        s3Client = S3FileClient()

        # generate a file name using timestamp
        file_name = f"album_art_{int(time.time())}.png"
        image_url_s3 = await s3Client.upload_image_from_url(
            image_url, file_name, "image/png"
        )

        return {"image": image_url_s3}

    async def chat_with_ask_iah_oracle(
        self,
        user_prompt: str,
        session_id: str,
        message_id: str,
        user_email: str,
    ):

        chat = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0.1, streaming=True)

        loaded_prompt = self.load_prompt_from_file_path(
            "prompts/ask_iah_system_prompt.yaml"
        )
        system_prompt = loaded_prompt.template

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    system_prompt,
                ),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
            ]
        )

        chain = prompt | chat

        history = await self.get_chat_message_history(session_id=session_id)

        chain_with_message_history = RunnableWithMessageHistory(
            chain,
            lambda session_id: history,
            input_messages_key="input",
            history_messages_key="chat_history",
        )

        stream = chain_with_message_history.astream(
            {"input": user_prompt}, {"configurable": {"session_id": session_id}}
        )

        all_responses = []
        async for response in stream:
            all_responses.append(response.content)
            yield response.content  # Yield each response for real-time processing

        # After the stream ends
        print("Streaming has ended. Total responses received:", len(all_responses))
        complete_output = "".join(all_responses)

        chat = CreateChatMessage(
            session_id=session_id,
            message_id=message_id,
            message=None,
            response=complete_output,
            is_user=False,
        )

        chat_service = ChatService(session=self.session)
        await chat_service.save_chat_message(user_email, chat)

        print("Complete stream output:")
        print(complete_output)

    async def check_user_prompt_request(
        self, user_prompt: str, session_id: str, message_id: str, email: str
    ) -> None:

        prompt = self.load_prompt_from_file_path("prompts/extract_metadata_prompt.yaml")

        llm = ChatOpenAI(model_name="gpt-4-turbo-preview", temperature=0)

        user_prompt_schema = {
            "type": "function",
            "function": {
                "name": "get_user_request",
                "description": "This function returns true or false for is_playlist, is_image, is_general_request,  based on the user prompt.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "is_playlist": {
                            "type": "boolean",
                            "description": "Indicates if the request is for a playlist",
                        },
                        "is_image": {
                            "type": "boolean",
                            "description": "Indicates if the request is for an image",
                        },
                        "is_general_request": {
                            "type": "boolean",
                            "description": "Indicates if the request is a general request",
                        },
                        "numbers_of_tracks": {
                            "type": "integer",
                            "description": "Numbers of tracks requested in the playlist",
                        },
                    },
                    "required": [
                        "is_playlist",
                        "is_image",
                        "is_general_request",
                        "numbers_of_tracks",
                    ],
                },
            },
        }

        structured_llm = create_structured_output_runnable(
            user_prompt_schema,
            llm,
            mode="openai-tools",
            enforce_function_usage=True,
            return_single=True,
        )
        chain = (
            RunnableParallel({"user_prompt": RunnablePassthrough()})
            | prompt
            | structured_llm
        )

        user_service = UserService(session=self.session)
        # # Question
        response = chain.invoke(user_prompt)
        track_ids = []
        image_url = None
        # decorate the user prompt based on the user request
        # user_prompt_deco = await self.decorate_user_prompt_request(user_prompt)
        if response["is_playlist"]:
            # run the similarity search for the playlist
            k = response["numbers_of_tracks"] if response["numbers_of_tracks"] else 10
            track_ids = await self.retrieve_related_tracks_based_on_prompt(
                user_prompt, k
            )
            update_key = UpdateAPIUsage(
                update_key=APIUsage.IAH_PLAYLIST_GENERATION.value,
            )
            await user_service.update_user_api_consumption(email, update_key)

        if response["is_image"]:
            # generate album art based on the user prompt
            image_url_response = await self.generate_square_album_art_based_on_prompt(
                user_prompt
            )
            image_url = image_url_response["image"]
            update_key = UpdateAPIUsage(
                update_key=APIUsage.IAH_IMAGE_GENERATION.value,
            )
            await user_service.update_user_api_consumption(email, update_key)

        return {
            "metadata": response,
            "track_ids": track_ids,
            "image_url": image_url,
            "session_id": session_id,
            "message_id": message_id,
        }

    async def decorate_user_prompt_request(self, user_prompt: str) -> str:
        chat = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0.1)

        loaded_prompt = self.load_prompt_from_file_path(
            "prompts/ask_iah_system_prompt.yaml"
        )
        system_prompt = loaded_prompt.template

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    system_prompt,
                ),
                ("human", "{input}"),
            ]
        )

        chain = prompt | chat | StrOutputParser()

        # get the response from langchain
        response = chain.invoke({"input": user_prompt})
        return response

    def load_prompt_from_file_path(self, file_path: str):
        script_path = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_path)
        target_file_path = os.path.join(script_dir, file_path)
        return load_prompt(target_file_path)

    async def reindex_all_metadata_for_tracks(
        self, background_tasks: BackgroundTasks
    ) -> None:
        track_records = await self.session.execute(select(Track))
        tracks = track_records.scalars().fetchall()

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

        self.logger.info(
            f"Tasks started, processing in the background found: {len(track_data)} tracks."
        )

        fist_ten = track_data[:10]
        background_tasks.add_task(
            self.process_data_in_background, track_data, background_tasks
        )

        return f"Tasks started, processing in the background found: {len(track_data)} tracks."

    async def generate_rag_from_user_prompt(
        self, user_prompt: str, k: int = 10
    ) -> List[str]:
        embeddings = OpenAIEmbeddings()
        index_name = "iah-tracks"
        vector_store = PineconeVectorStore.from_existing_index(
            index_name=index_name, embedding=embeddings
        )

        retriever = vector_store.as_retriever(search_kwargs={"k": 20})

        template = """
        this is what user requested: {user_prompt}
        based on user request filter out most suitable 10 tracks. when
        selecting the tracks always try to select from multiple collections. here is the context to select from
        NOTE: select the most suitable 10 tracks
        {context}
        """
        prompt = ChatPromptTemplate.from_template(template)

        llm = ChatOpenAI(model_name="gpt-4-turbo-preview", temperature=0)

        track_id_schema = {
            "type": "function",
            "function": {
                "name": "get_track_ids",
                "description": "Return 10 the list of track ids as a string array.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "track_ids": {
                            "description": "String array of track ids",
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["track_ids"],
                },
            },
        }

        structured_llm = create_structured_output_runnable(
            track_id_schema,
            llm,
            mode="openai-tools",
            enforce_function_usage=True,
            return_single=True,
        )
        chain = (
            RunnableParallel(
                {"context": retriever, "user_prompt": RunnablePassthrough()}
            )
            | prompt
            | structured_llm
        )

        response = chain.invoke(user_prompt)
        return response

    async def retrieve_related_collection_based_on_prompt(
        self, user_prompt: str
    ) -> None:

        # first select the vector database
        embeddings = OpenAIEmbeddings()
        index_name = "collections"

        vector_store = PineconeVectorStore.from_existing_index(
            index_name=index_name, embedding=embeddings
        )
        retriever = vector_store.as_retriever(
            search_type="mmr", search_kwargs={"k": 6, "lambda_mult": 0.25}
        )
        similar_collections = retriever.get_relevant_documents(user_prompt)

        return similar_collections

    async def retrieve_related_fom_pgvector_collection_based_on_prompt(
        self, user_prompt: str
    ) -> List[str]:

        # first select the vector database
        embeddings = OpenAIEmbeddings()
        query_embedding = embeddings.embed_query(user_prompt)
        K = 6

        result = await self.session.execute(
            select(
                CollectionEmbedding.collection_id,
                CollectionEmbedding.embedding.cosine_distance(query_embedding).label(
                    "distance"
                ),
            )
            .order_by("distance")
            .limit(K)
        )

        similar_collection_ids = [str(row.collection_id) for row in result.fetchall()]

        return similar_collection_ids

    async def retrieve_related_tracks_based_on_prompt_using_pgvector(
        self, user_prompt: str, k: int = 20
    ) -> List[str]:

        collection_ids = (
            await self.retrieve_related_fom_pgvector_collection_based_on_prompt(
                user_prompt=user_prompt
            )
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

        # Step 5: Randomize the track IDs (if needed)
        random.shuffle(similar_track_ids)

        return similar_track_ids

    async def retrieve_related_tracks_based_on_prompt(
        self, user_prompt: str, k: int = 20
    ) -> List[str]:

        # first get the related collections from vector database
        collections = await self.retrieve_related_collection_based_on_prompt(
            user_prompt
        )

        collection_ids = []
        for collection in collections:
            collection_ids.append(collection.metadata["collection_id"])

        # get collection list by pg vector search
        collection_ids = (
            await self.retrieve_related_fom_pgvector_collection_based_on_prompt(
                user_prompt=user_prompt
            )
        )
        # then select track based on the collections and user prompt
        embeddings = OpenAIEmbeddings()
        index_name = "tracks"

        vector_store = PineconeVectorStore.from_existing_index(
            index_name=index_name, embedding=embeddings
        )
        retriever = vector_store.as_retriever(
            search_kwargs={"k": k, "filter": {"collection_id": {"$in": collection_ids}}}
        )
        similar_tracks = retriever.get_relevant_documents(user_prompt)

        track_ids = []
        for track in similar_tracks:
            track_ids.append(track.metadata["track_id"])

        # randomize the track ids
        random.shuffle(track_ids)
        return track_ids

    async def check_image_resonance_user_prompt(
        self,
        user_prompt: str,
        aspect_ratio: str,
        art_style: str,
        art_style_description: str,
        session_id: str,
        message_id: str,
        email: str,
    ) -> None:

        prompt = self.load_prompt_from_file_path("prompts/extract_metadata_prompt.yaml")

        llm = ChatOpenAI(model_name="gpt-4-turbo-preview", temperature=0)

        user_prompt_schema = {
            "type": "function",
            "function": {
                "name": "get_user_request",
                "description": "This function returns true or false for is_playlist, is_image, is_general_request,  based on the user prompt.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "is_playlist": {
                            "type": "boolean",
                            "description": "Indicates if the request is for a playlist",
                        },
                        "is_image": {
                            "type": "boolean",
                            "description": "Indicates if the request is for an image",
                        },
                        "is_general_request": {
                            "type": "boolean",
                            "description": "Indicates if the request is a general request",
                        },
                        "numbers_of_tracks": {
                            "type": "integer",
                            "description": "Numbers of tracks requested in the playlist",
                        },
                    },
                    "required": [
                        "is_playlist",
                        "is_image",
                        "is_general_request",
                        "numbers_of_tracks",
                    ],
                },
            },
        }

        structured_llm = create_structured_output_runnable(
            user_prompt_schema,
            llm,
            mode="openai-tools",
            enforce_function_usage=True,
            return_single=True,
        )
        chain = (
            RunnableParallel({"user_prompt": RunnablePassthrough()})
            | prompt
            | structured_llm
        )

        user_service = UserService(session=self.session)
        # # Question
        response = chain.invoke(user_prompt)
        track_ids = []
        image_url = None
        # decorate the user prompt based on the user request
        # user_prompt_deco = await self.decorate_user_prompt_request(user_prompt)
        if response["is_playlist"]:
            # run the similarity search for the playlist
            k = response["numbers_of_tracks"] if response["numbers_of_tracks"] else 10
            track_ids = await self.retrieve_related_tracks_based_on_prompt(
                user_prompt, k
            )
            update_key = UpdateAPIUsage(
                update_key=APIUsage.IAH_PLAYLIST_GENERATION.value,
            )
            await user_service.update_user_api_consumption(email, update_key)

        if aspect_ratio != "" and art_style != "" and art_style_description != "":
            # generate album art based on the user prompt
            image_url_response = await self.generate_resonance_art(
                user_prompt=user_prompt,
                aspect_ratio=aspect_ratio,
                art_style=art_style,
                art_style_description=art_style_description,
            )
            image_url = image_url_response["image"]
            update_key = UpdateAPIUsage(
                update_key=APIUsage.IAH_IMAGE_GENERATION.value,
            )
            await user_service.update_user_api_consumption(email, update_key)

        return {
            "metadata": response,
            "track_ids": track_ids,
            "image_url": image_url,
            "session_id": session_id,
            "message_id": message_id,
        }

    async def generate_resonance_art(
        self,
        user_prompt: str,
        aspect_ratio: str,
        art_style: str,
        art_style_description: str,
    ) -> None:

        image_size = "1024x1024"
        resize_resolution = None
        if aspect_ratio == "1:1":
            image_size = "1024x1024"
            resize_resolution = None
        elif aspect_ratio == "16:9":
            image_size = "1792x1024"
            resize_resolution = None
        elif aspect_ratio == "3:4":
            image_size = "1024x1792"
            resize_resolution = "1024x1400"
        elif aspect_ratio == "4:3":
            image_size = "1792x1024"
            resize_resolution = "1792x1400"
        elif aspect_ratio == "9:16":
            image_size = "1024x1792"

        image_prompt = f"""
            user prompt: {user_prompt}
            art style: {art_style}
            art style description: {art_style_description}
            Please generate an image based on the user prompt
        """
        llm = LangChainOpenAI(temperature=0.9)
        prompt = self.load_prompt_from_file_path("prompts/image_generation_prompt.yaml")
        chain = RunnableParallel({"image_desc": RunnablePassthrough()}) | prompt | llm
        image_url = DallEAPIWrapper(
            model="dall-e-3",
            size=image_size,
        ).run(chain.invoke(image_prompt))

        # download the image and upload into the s3 bucket
        s3Client = S3FileClient()
        if resize_resolution:
            response = requests.get(image_url)
            response.raise_for_status()
            with Image.open(BytesIO(response.content)) as img:
                # Parse the target dimensions from the resolution string
                target_width, target_height = map(int, resize_resolution.split("x"))

                # Calculate the target aspect ratio
                target_ratio = target_width / target_height

                # Calculate the original dimensions and aspect ratio
                original_width, original_height = img.size
                original_ratio = original_width / original_height

                # Determine dimensions of the new crop area based on the target ratio
                if original_ratio > target_ratio:
                    # Original is wider than target ratio
                    new_height = original_height
                    new_width = int(target_ratio * new_height)
                else:
                    # Original is taller than target ratio
                    new_width = original_width
                    new_height = int(new_width / target_ratio)

                # Calculate the position to start cropping from (center the crop)
                left = (original_width - new_width) // 2
                top = (original_height - new_height) // 2

                # Perform the crop
                cropped_img = img.crop((left, top, left + new_width, top + new_height))

                # Save the cropped image to a BytesIO object
                img_byte_arr = BytesIO()
                cropped_img.save(img_byte_arr, format="PNG")  # Save as PNG
                img_byte_arr.seek(0)
                file_name = f"spectral_resonance_art_{int(time.time())}.png"
                image_url_s3 = s3Client.upload_file_object_to_s3(
                    file_name, img_byte_arr, "image/png"
                )
                return {"image": image_url_s3}

        else:
            # generate a file name using timestamp
            file_name = f"spectral_resonance_art_{int(time.time())}.png"
            image_url_s3 = await s3Client.upload_image_from_url(
                image_url, file_name, "image/png"
            )
            return {"image": image_url_s3}

    async def get_chat_message_history(self, session_id: str) -> dict:
        chat_query = select(ChatHistory).where(ChatHistory.session_id == session_id)
        chat_record = await self.session.execute(chat_query)
        chat_history: list[ChatHistory] = chat_record.scalars().all()

        langchain_chat_history = ChatMessageHistory()
        for chat in chat_history:
            if chat.is_user:
                if chat.message:
                    langchain_chat_history.add_user_message(chat.message)
            else:
                if chat.response:
                    langchain_chat_history.add_ai_message(chat.response)
        print(langchain_chat_history)
        return langchain_chat_history
