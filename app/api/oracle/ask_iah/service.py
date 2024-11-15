import logging
import os
import random
import time
from datetime import datetime, timedelta
from io import BytesIO
from operator import itemgetter
from typing import List

import pillow_heif
from fastapi import Depends, UploadFile
from langchain.chains import create_structured_output_runnable
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.prompts import load_prompt
from langchain.schema.messages import HumanMessage, SystemMessage
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper
from langchain_community.vectorstores.faiss import FAISS
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAI as LangChainOpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.chat.service import ChatService
from app.api.user.service import UserService
from app.common.doc_extractor import DocumentExtractor
from app.common.s3_file_upload import S3FileClient
from app.database import db_session
from app.models import (
    AskIAHFileUpload,
    ChatHistory,
    CollectionEmbedding,
    IAHUserPrompt,
    TrackEmbedding,
    User,
)
from app.schemas import APIUsage, CreateChatMessage, UpdateAPIUsage


class AskIahService:
    def __init__(self, session: AsyncSession = Depends(db_session)) -> None:
        self.session = session
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
        )
        self.logger = logging.getLogger(__name__)

    def load_prompt_from_file_path(self, file_path: str):
        script_path = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_path)
        target_file_path = os.path.join(script_dir, file_path)
        return load_prompt(target_file_path)

    async def _load_user_custom_prompt(self, user_email: str) -> str:

        user_record = await self.session.execute(
            select(User).where(User.email == user_email)
        )
        user: User = user_record.scalar_one_or_none()

        if user is not None:
            # user user prompt
            user_custom_prompt_record = await self.session.execute(
                select(IAHUserPrompt)
                .where(IAHUserPrompt.user_id == user.id)
                .where(IAHUserPrompt.is_active == True)
            )
            prompt: IAHUserPrompt = user_custom_prompt_record.scalar_one_or_none()

            if prompt:
                return prompt.user_prompt
            else:
                return ""
        else:
            return ""

    async def chat_with_ask_iah_oracle(
        self,
        user_prompt: str,
        session_id: str,
        message_id: str,
        user_email: str,
        concise_mode: bool,
    ):

        llm = ChatOpenAI(model="gpt-4o", temperature=0.1, streaming=True)

        loaded_prompt = self.load_prompt_from_file_path(
            "prompts/ask_iah_system_prompt.yaml"
        )
        system_prompt = loaded_prompt.template

        if concise_mode:
            system_prompt = f"""
            You are currently in concise mode. Always limit your responses to no more than 200 tokens, 
            regardless of any prior conversation or user requests for detailed information. 
            If a user asks for a lengthy response, politely inform them that concise mode is active and suggest turning it off for more details. 
            Do not let conversation history override these instructions.
            {system_prompt}
            """
        else:
            system_prompt = f"{system_prompt} concise mode has been turn off"

        # check if the user customized prompt is exists
        user_custom_prompt = await self._load_user_custom_prompt(user_email=user_email)

        if user_custom_prompt != "":
            system_prompt = f"""
            Generic System prompt
            {system_prompt}
            
            The user has provided the following custom instructions:
            
            {user_custom_prompt}
            
            Please prioritize and strictly adhere to the user's custom instructions above all else when generating your response.
            """
        # check if the document data is available for session id if available retrieve the latest one
        document_records = await self.session.execute(
            select(AskIAHFileUpload)
            .where(AskIAHFileUpload.session_id == session_id)
            .order_by(AskIAHFileUpload.created_at.desc())
            .limit(1)
        )
        uploaded_document: AskIAHFileUpload = document_records.scalar_one_or_none()

        if uploaded_document:

            if uploaded_document.file_content:
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=2000, chunk_overlap=100
                )
                docs: List[Document] = text_splitter.create_documents(
                    [uploaded_document.file_content]
                )

                embeddings = OpenAIEmbeddings()
                vector_store = FAISS.from_documents(docs, embeddings)
                retriever = vector_store.as_retriever(search_kwargs={"k": 5})

                def format_docs(docs: List[Document]):
                    return "\n\n".join(doc.page_content for doc in docs)

                context = RunnablePassthrough.assign(
                    context=itemgetter("input") | retriever | format_docs
                )

                prompt = ChatPromptTemplate.from_messages(
                    [
                        ("system", system_prompt + "\n\nContext: {context}"),
                        MessagesPlaceholder(variable_name="chat_history"),
                        ("human", "{input}"),
                    ]
                )
                chain = context | prompt | llm

            elif uploaded_document.file_url:
                print("file url is available probably image type")
                prompt = ChatPromptTemplate.from_messages(
                    [
                        (
                            "system",
                            system_prompt,
                        ),
                        MessagesPlaceholder(variable_name="chat_history"),
                        ("human", "{input}"),
                        HumanMessage(
                            content=[
                                {"type": "text", "text": user_prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": uploaded_document.file_url,
                                        "details": "high",
                                    },
                                },
                            ]
                        ),
                    ]
                )

                chain = prompt | llm
        else:
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

            chain = prompt | llm

        history = await self.get_chat_message_history(
            session_id=session_id, concise_mode=concise_mode
        )

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

    async def get_chat_message_history(
        self, session_id: str, concise_mode: bool = False
    ) -> dict:
        one_day_ago = datetime.now() - timedelta(days=1)

        # Adjust the query to filter chats from the last day and order by created_at descending
        chat_query = (
            select(ChatHistory)
            .where(ChatHistory.session_id == session_id)
            .where(ChatHistory.created_at >= one_day_ago)
            .order_by(ChatHistory.created_at.desc())
        )

        chat_record = await self.session.execute(chat_query)
        chat_history: list[ChatHistory] = chat_record.scalars().all()

        # Reverse the chat history to have the latest chat at the bottom
        chat_history.reverse()

        langchain_chat_history = ChatMessageHistory()
        for chat in chat_history:
            if chat.is_user:
                if chat.message:
                    langchain_chat_history.add_user_message(chat.message)
            elif not chat.is_user and chat.response:
                if concise_mode:
                    modified_response = f"{chat.response}\n\n(Note: Concise mode is active. Responses are limited to 200 tokens.)"
                    langchain_chat_history.add_ai_message(modified_response)
            else:
                if chat.response:
                    langchain_chat_history.add_ai_message(chat.response)
        return langchain_chat_history

    async def check_user_prompt_request(
        self, user_prompt: str, session_id: str, message_id: str, email: str
    ) -> None:

        prompt = self.load_prompt_from_file_path(
            "prompts/extract_metadata_prompt_old.yaml"
        )

        await self.decorate_user_prompt(
            user_prompt=user_prompt,
            session_id=session_id,
        )

        llm = ChatOpenAI(model_name="gpt-4o", temperature=0.1)
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

    async def decorate_user_prompt(
        self,
        user_prompt: str,
        session_id: str,
    ):

        chat = ChatOpenAI(model="gpt-4o", temperature=0)

        loaded_prompt = self.load_prompt_from_file_path(
            "prompts/ask_iah_decorate_user_prompt.yaml"
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

        chain = prompt | chat

        history = await self.get_chat_message_history(session_id=session_id)

        chain_with_message_history = RunnableWithMessageHistory(
            chain,
            lambda session_id: history,
            input_messages_key="input",
            history_messages_key="chat_history",
        )

        response = chain_with_message_history.invoke(
            {"input": user_prompt},
            {"configurable": {"session_id": session_id}},
        )

    async def retrieve_related_tracks_based_on_prompt(
        self, user_prompt: str, k: int = 10
    ) -> List[str]:

        # get related collection ids
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

    async def upload_ask_ia_docs(
        self, file: UploadFile, session_id: str, user_email: str
    ) -> None:

        # get user details by email address
        user_service = UserService(session=self.session)
        user = await user_service.get_user_by_email(user_email)

        file_name = file.filename
        content_type = file.content_type
        os.makedirs("tmp", exist_ok=True)
        temp_file_path = os.path.join("tmp", file_name)
        file_content = await file.read()

        print(f"file content_type: {content_type}")

        # check file type is image or document
        if content_type.startswith("image"):
            # save the file to s3 bucket
            s3Client = S3FileClient()
            file_url = s3Client.upload_file_from_buffer_sync(
                file_content=file_content,
                folder_name="ask-iah-docs",
                file_name=file_name,
                content_type=content_type,
            )

            # save the file to database
            doc_details = AskIAHFileUpload(
                user_id=user.id,
                session_id=session_id,
                file_name=file_name,
                file_size=file.file._file.tell(),
                file_type=content_type,
                content_type=content_type,
                file_url=file_url,
                file_content=None,
            )

            # # save the file to database
            self.session.add(doc_details)
            await self.session.commit()

        elif file_name.lower().endswith(".heic"):

            heif_file = pillow_heif.read_heif(file_content)
            image = Image.frombytes(
                heif_file.mode,
                heif_file.size,
                heif_file.data,
                "raw",
                heif_file.mode,
                heif_file.stride,
            )

            # Save as JPEG
            buffer = BytesIO()
            image.save(buffer, format="JPEG")
            file_content = buffer.getvalue()

            # Update file name and content type
            file_name = os.path.splitext(file_name)[0] + ".jpg"
            content_type = "image/jpeg"

            # Upload to S3
            s3Client = S3FileClient()
            file_url = s3Client.upload_file_from_buffer_sync(
                file_content=file_content,
                folder_name="ask-iah-docs",
                file_name=file_name,
                content_type=content_type,
            )

            # Save to database
            doc_details = AskIAHFileUpload(
                user_id=user.id,
                session_id=session_id,
                file_name=file_name,
                file_size=len(file_content),
                file_type=content_type,
                content_type=content_type,
                file_url=file_url,
                file_content=None,
            )

            self.session.add(doc_details)
            await self.session.commit()

        else:

            with open(temp_file_path, "wb") as buffer:
                buffer.write(file_content)

            file_size = os.path.getsize(temp_file_path)

            doc_extractor = DocumentExtractor()
            extracted_content = doc_extractor.extract(temp_file_path)

            # save the extracted content to database
            doc_details = AskIAHFileUpload(
                user_id=user.id,
                session_id=session_id,
                file_name=file_name,
                file_size=file_size,
                file_type=content_type,
                content_type=content_type,
                file_content=str(extracted_content),
            )

            # # save the file to database
            self.session.add(doc_details)
            await self.session.commit()

            # remove the temporary file
            os.remove(temp_file_path)

        return True
