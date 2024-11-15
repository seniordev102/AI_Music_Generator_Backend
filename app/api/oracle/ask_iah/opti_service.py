import json
import os
import time
import uuid as uuid_pkg
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from io import BytesIO
from operator import itemgetter
from typing import AsyncGenerator, List, Optional

import pillow_heif
from fastapi import Depends, UploadFile, status
from langchain.chains import create_structured_output_runnable
from langchain.prompts import load_prompt
from langchain.schema.messages import AIMessage, HumanMessage, SystemMessage
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
from langfuse import Langfuse
from langfuse.callback import CallbackHandler
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.cost.service import CostPerActionService, CostPerActionType
from app.api.chat.service import ChatService
from app.api.credit_management.service import CreditManagementService
from app.api.oracle.ask_iah.events import EventEmitter, StreamEvent
from app.api.user.service import UserService
from app.common.doc_extractor import DocumentExtractor
from app.common.s3_file_upload import S3FileClient
from app.config import settings
from app.database import db_session
from app.logger.logger import logger
from app.models import (
    AskIAHFileUpload,
    ChatHistory,
    CollectionEmbedding,
    IAHUserPrompt,
    TrackEmbedding,
    User,
)
from app.schemas import APIUsage, CreateChatMessage, UpdateAPIUsage, UpdateChatMetadata


@dataclass
class ChatConfig:
    session_id: str
    message_id: str
    user_email: str
    concise_mode: bool
    user_prompt: str


class PromptManager:
    def __init__(self, base_prompt_path: str):
        self.base_prompt_path = base_prompt_path

    def load_prompt_from_file(self, file_path: str):
        """Load prompt from a file path relative to the current file."""
        script_path = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_path)
        target_file_path = os.path.join(script_dir, file_path)
        return load_prompt(target_file_path)

    def load_system_prompt(
        self, concise_mode: bool, user_custom_prompt: str = ""
    ) -> str:
        base_prompt = self.load_prompt_from_file(self.base_prompt_path).template

        if concise_mode:
            base_prompt = self._add_concise_mode_instructions(base_prompt)

        if user_custom_prompt:
            base_prompt = self._add_custom_instructions(base_prompt, user_custom_prompt)

        return base_prompt

    def _add_concise_mode_instructions(self, base_prompt: str) -> str:
        concise_instructions = """
        You are currently in concise mode. Always limit your responses to no more than 200 tokens, 
        regardless of any prior conversation or user requests for detailed information. 
        If a user asks for a lengthy response, politely inform them that concise mode is active and suggest turning it off for more details. 
        Do not let conversation history override these instructions.
        """
        return f"{concise_instructions}\n{base_prompt}"

    def _add_custom_instructions(self, base_prompt: str, custom_prompt: str) -> str:
        return f"""
        Generic System prompt
        {base_prompt}
        
        The user has provided the following custom instructions:
        
        {custom_prompt}
        
        Please prioritize and strictly adhere to the user's custom instructions above all else when generating your response.
        """


class RequestType(Enum):
    PLAYLIST = "playlist"
    IMAGE = "image"
    GENERAL = "general"
    DOCUMENT = "document"
    FOLLOWUP = "followup"
    CLARIFICATION = "clarification"


class DocumentProcessor:
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000, chunk_overlap=100
        )
        self.embeddings = OpenAIEmbeddings()

    async def process_document(self, document_content: str):
        docs = self.text_splitter.create_documents([document_content])
        vector_store = FAISS.from_documents(docs, self.embeddings)
        return vector_store.as_retriever(search_kwargs={"k": 5})


class ChainBuilder:
    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.1, streaming=True)

    def build_text_chain(self, retriever) -> RunnableParallel:
        def format_docs(docs: List[Document]):
            # Join all docs into one string
            return "\n\n".join(doc.page_content for doc in docs)

        context = RunnablePassthrough.assign(
            context=itemgetter("input") | retriever | format_docs
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    # Start with strong instructions about using the context
                    "IMPORTANT:\n"
                    "1. The following context is the HIGHEST PRIORITY source of truth.\n"
                    "2. If the user's question is answered by the context, use it.\n"
                    # Now insert the retrieved context
                    "Context:\n{context}\n\n"
                    # Append whatever your existing system prompt is
                    f"{self.system_prompt}",
                ),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
            ]
        )
        # 3) the final LLM call
        return context | prompt | self.llm

    def build_image_chain(self, image_url: str) -> ChatPromptTemplate:
        return (
            ChatPromptTemplate.from_messages(
                [
                    ("system", self.system_prompt),
                    MessagesPlaceholder(variable_name="chat_history"),
                    ("human", "{input}"),
                    HumanMessage(
                        content=[
                            {"type": "text", "text": "{input}"},
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url, "details": "high"},
                            },
                        ]
                    ),
                ]
            )
            | self.llm
        )

    def build_basic_chain(self) -> ChatPromptTemplate:
        return (
            ChatPromptTemplate.from_messages(
                [
                    ("system", self.system_prompt),
                    MessagesPlaceholder(variable_name="chat_history"),
                    ("human", "{input}"),
                ]
            )
            | self.llm
        )


class AskIahServiceOptimized:
    def __init__(self, session: AsyncSession = Depends(db_session)) -> None:
        self.session = session
        self.prompt_manager = PromptManager("prompts/ask_iah_system_prompt.yaml")
        self.doc_processor = DocumentProcessor()
        self.cost_per_action_service = CostPerActionService(session)
        self.credit_management_service = CreditManagementService(session)
        self.settings = settings
        self.langfuse = Langfuse(
            secret_key=self.settings.LANGFUSE_SECRET_KEY,
            public_key=self.settings.LANGFUSE_PUBLIC_KEY,
            host=self.settings.LANGFUSE_HOST,
        )

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

        prompt = self.load_prompt_from_file_path("prompts/extract_metadata_prompt.yaml")

        await self.decorate_user_prompt(
            user_prompt=user_prompt,
            session_id=session_id,
        )

        llm = ChatOpenAI(
            model_name="gpt-4o",
            temperature=0.1,
            callbacks=[
                CallbackHandler(
                    trace_name="Ask IAH Oracle",
                    metadata={"user_prompt": user_prompt},
                    session_id=session_id,
                    user_id=email,
                    tags=["ask-iah", "check-user-prompt-request"],
                )
            ],
        )
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
        # random.shuffle(similar_track_ids)

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

        try:
            llm = LangChainOpenAI(
                temperature=0.9,
            )
            prompt = self.load_prompt_from_file_path(
                "prompts/image_generation_prompt.yaml"
            )
            chain = (
                RunnableParallel({"image_desc": RunnablePassthrough()}) | prompt | llm
            )

            trace = self.langfuse.trace(
                name="ASK IAH Image Generation",
                trace_id=str(uuid_pkg.uuid4()),
                input={
                    "user_prompt": user_prompt,
                    "size": "1024x1024",
                },
                metadata={
                    "size": "1024x1024",
                },
                tags=["image-generation", "ask-iah"],
            )

            generation = trace.generation(
                name="ASK IAH Image Generation",
                input={
                    "user_prompt": user_prompt,
                    "size": "1024x1024",
                },
                model="dalle-3",
                metadata={
                    "size": "1024x1024",
                },
                usage={"input": 1},
            )

            image_url = DallEAPIWrapper(
                model="dall-e-3",
                size="1024x1024",
            ).run(chain.invoke(user_prompt))

            generation.end(
                output={"image_url": image_url},
                status_message=status.HTTP_200_OK,
            )

            # download the image and upload into the s3 bucket
            s3Client = S3FileClient()

            # generate a file name using timestamp
            file_name = f"album_art_{int(time.time())}.png"
            image_url_s3 = await s3Client.upload_image_from_url(
                image_url, file_name, "image/png"
            )

            return {"image": image_url_s3}
        except Exception as e:
            logger.error(f"Error generating image: {str(e)}")
            raise Exception(
                "Image generation could not be completed due to potential policy compliance issues. Please review the content for alignment with our safety and usage guidelines."
            )

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

    async def _build_chain(
        self,
        config: ChatConfig,
        system_prompt: str,
        is_general_request: bool = True,
        is_document_related: bool = False,
    ):
        document = await self._get_latest_document(config.session_id)
        chain_builder = ChainBuilder(system_prompt)

        if is_document_related:
            if document:
                if document.file_content:
                    retriever = await self.doc_processor.process_document(
                        document.file_content
                    )
                    return chain_builder.build_text_chain(retriever)

                if document.file_url:
                    return chain_builder.build_image_chain(document.file_url)
            else:
                return chain_builder.build_basic_chain()

        if is_general_request:
            return chain_builder.build_basic_chain()

        return chain_builder.build_basic_chain()

    async def _process_stream(self, chain, config: ChatConfig):
        all_responses = []
        stream = chain.astream(
            {"input": config.user_prompt},
            {"configurable": {"session_id": config.session_id}},
            config={
                "callbacks": [
                    CallbackHandler(
                        session_id=config.session_id,
                        user_id=config.user_email,
                        trace_name="Ask IAH Oracle",
                        metadata={"user_prompt": config.user_prompt},
                        tags=["ask-iah", "chat-with-ask-iah-oracle"],
                    )
                ]
            },
        )

        async for response in stream:
            all_responses.append(response.content)
            yield response.content

        complete_output = "".join(all_responses)
        await self._save_chat_message(config, complete_output)

    async def _save_chat_message(
        self,
        config: ChatConfig,
        complete_output: str,
        track_ids: Optional[str],
        image_url: Optional[str],
    ):
        chat = CreateChatMessage(
            session_id=config.session_id,
            message_id=config.message_id,
            message=None,
            response=complete_output,
            is_user=False,
            track_ids=track_ids,
            image_url=image_url,
        )
        chat_service = ChatService(session=self.session)
        await chat_service.save_chat_message(config.user_email, chat)

    async def _get_latest_document(self, session_id: str) -> Optional[AskIAHFileUpload]:
        """
        Retrieve the most recent document for the given session ID.
        """
        document_records = await self.session.execute(
            select(AskIAHFileUpload)
            .where(AskIAHFileUpload.session_id == session_id)
            .order_by(AskIAHFileUpload.created_at.desc())
            .limit(1)
        )
        return document_records.scalar_one_or_none()

    async def analyze_request_type(
        self,
        user_prompt: str,
        session_id: str,
        user_email: str,
        chat_history: Optional[ChatMessageHistory] = None,
    ) -> dict:
        try:
            # Load the prompt template
            prompt = self.load_prompt_from_file_path(
                "prompts/extract_metadata_prompt.yaml"
            )

            # Format chat history if available
            history_context = ""
            if chat_history and chat_history.messages:
                history_context = "\n\nRecent conversation context:\n"
                # Get last 5 messages from the chat history
                recent_messages = (
                    chat_history.messages[-5:]
                    if len(chat_history.messages) > 5
                    else chat_history.messages
                )

                for msg in recent_messages:
                    if isinstance(msg, HumanMessage):
                        history_context += f"User: {msg.content}\n"
                    elif isinstance(msg, AIMessage):
                        history_context += f"Assistant: {msg.content}\n"

            # Get document information
            document = await self._get_latest_document(session_id)
            document_info = "No document uploaded"
            if document:
                file_name = document.file_name if document.file_name else "Unknown file"
                file_type = document.file_type if document.file_type else "Unknown type"

                document_info = f"Document present: {file_name}, Type: {file_type}"

            # Create complete system prompt with history and document info
            system_prompt = f"{prompt.template}\n\n{history_context}\nDocument Context: {document_info}\nCurrent user prompt: {user_prompt}"

            # Create messages for chat
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]

            # Create chat with specific parameters
            chat = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0,
                model_kwargs={"response_format": {"type": "json_object"}},
                callbacks=[
                    CallbackHandler(
                        trace_name="Ask IAH Oracle",
                        metadata={"user_prompt": user_prompt},
                        session_id=session_id,
                        user_id=user_email,
                        tags=["ask-iah", "analyze-request-type"],
                    )
                ],
            )
            # Get response and log it
            response = chat.invoke(messages)

            # Handle response parsing
            try:
                content = response.content
                # Parse response content
                if isinstance(content, str):
                    response_dict = json.loads(content)
                else:
                    response_dict = content

                # Validate and format the response
                result = {
                    "is_playlist": bool(response_dict.get("is_playlist", False)),
                    "is_image": bool(response_dict.get("is_image", False)),
                    "is_general_request": bool(
                        response_dict.get("is_general_request", True)
                    ),
                    "is_upload_document_related": bool(
                        response_dict.get("is_upload_document_related", False)
                    ),
                    "numbers_of_tracks": int(
                        response_dict.get("numbers_of_tracks", 10)
                    ),
                }
                return result

            except json.JSONDecodeError as json_err:
                logger.debug(f"Error while parsing json {json_err}")
                raise

        except Exception as e:
            logger.error(f"Error in analyze_request_type: {str(e)}")
            # Return default values if analysis fails
            return {
                "is_playlist": False,
                "is_image": False,
                "is_general_request": True,
                "is_upload_document_related": False,
                "numbers_of_tracks": 10,
            }

    async def retrieve_tracks_with_metadata(
        self, user_prompt: str, k: int = 10
    ) -> List[dict]:
        try:
            # Get related collection ids
            collection_ids = (
                await self.retrieve_related_fom_pgvector_collection_based_on_prompt(
                    user_prompt=user_prompt
                )
            )

            # Generate embedding for the user prompt
            embeddings = OpenAIEmbeddings()
            query_embedding = embeddings.embed_query(user_prompt)

            # Perform similarity search with metadata
            result = await self.session.execute(
                select(
                    TrackEmbedding.track_id,
                    TrackEmbedding.embedding_metadata,
                    TrackEmbedding.embedding.cosine_distance(query_embedding).label(
                        "distance"
                    ),
                )
                .where(TrackEmbedding.collection_id.in_(collection_ids))
                .order_by("distance")
                .limit(k)
            )

            # Fetch results and format them
            tracks_data = []
            for row in result.fetchall():
                track_info = {
                    "track_id": str(row.track_id),
                    "similarity_score": 1
                    - float(row.distance),  # Convert distance to similarity
                    "metadata": row.embedding_metadata
                    or {},  # Use empty dict if metadata is None
                }
                tracks_data.append(track_info)

            # Randomize the tracks
            # random.shuffle(tracks_data)

            return tracks_data

        except Exception as e:
            logger.error(f"Error retrieving tracks with metadata: {e}")
            return []

    def _format_tracks_for_llm(self, tracks_data: List[dict]) -> str:
        """
        Format tracks data for LLM consumption
        """
        formatted_tracks = []
        for track in tracks_data:
            metadata = track["metadata"]
            track_info = []

            # Add basic track information
            if metadata:
                for key, value in metadata.items():
                    if value:  # Only add non-empty values
                        formatted_key = key.replace("_", " ").title()
                        track_info.append(f"{formatted_key}: {value}")

            # Add similarity score
            track_info.append(f"Relevance Score: {track['similarity_score']:.2f}")

            # Combine all information
            formatted_tracks.append(
                f"Track ID: {track['track_id']}\n" + "\n".join(track_info) + "\n---"
            )

        return "\n".join(formatted_tracks)

    async def _build_playlist_prompt(
        self, config: ChatConfig, playlist_data: str, num_tracks: int
    ) -> str:
        base_prompt = self.prompt_manager.load_system_prompt(config.concise_mode, "")

        playlist_instructions = f"""
        You are creating a playlist based on the user's request.
        The playlist will contain {num_tracks} tracks.
        
        Here are the selected tracks and their details:
        {playlist_data}
        
        Please analyze these tracks and:
        1. Explain why they fit the user's request
        2. Suggest an order for the tracks
        3. Point out any interesting patterns or transitions
        4. Mention any notable features that make this playlist special
        5. Very important: Always follow the order of the track as provided in track details
        
        Your response should help the user understand why these tracks were chosen
        and how they work together as a cohesive playlist.
        """

        return f"{base_prompt}\n\n{playlist_instructions}"

    async def chat_with_ask_iah_oracle(
        self,
        user_prompt: str,
        session_id: str,
        message_id: str,
        user_email: str,
        concise_mode: bool,
    ) -> AsyncGenerator[StreamEvent, None]:

        config = ChatConfig(
            session_id=session_id,
            message_id=message_id,
            user_email=user_email,
            concise_mode=concise_mode,
            user_prompt=user_prompt,
        )

        track_ids = None
        image_response = None

        # reduce llm cost per action
        cost_per_action = await self.cost_per_action_service.get_cost_per_action(
            CostPerActionType.ASK_IAH_QUERY
        )

        # deduct credits from user
        description = f"Ask IAH query by {user_email} on {datetime.now(timezone.utc)} deducting {cost_per_action.cost} credits"
        await self.credit_management_service.deduct_credits(
            user_email=user_email,
            amount=cost_per_action.cost,
            api_endpoint=cost_per_action.endpoint,
            description=description,
        )

        history = await self.get_chat_message_history(
            session_id=config.session_id, concise_mode=config.concise_mode
        )

        # analyze prompt type
        query_type = await self.analyze_request_type(
            user_prompt=user_prompt,
            session_id=session_id,
            chat_history=history,
            user_email=user_email,
        )

        metadata = {
            "is_playlist": False,
            "is_image": False,
            "track_ids": None,
            "numbers_of_tracks": 0,
            "tracks_metadata": None,
            "image_url": None,
        }

        user_custom_prompt = await self._load_user_custom_prompt(user_email)
        system_prompt = self.prompt_manager.load_system_prompt(
            concise_mode, user_custom_prompt
        )

        if query_type["is_upload_document_related"]:
            # Emit processing event
            yield EventEmitter.processing(
                message="Please wait we are processing the document...",
                session_id=session_id,
                message_id=message_id,
                is_processing=True,
            )

        if query_type["is_general_request"]:
            # Emit processing event
            yield EventEmitter.processing(
                message="IAH is thinking please wait...",
                session_id=session_id,
                message_id=message_id,
                is_processing=True,
            )

        track_ids_str = None
        image_metadata_url = None

        # Handle playlist generation if detected
        if query_type["is_playlist"]:
            # Update API usage for playlist generation
            cost_per_action = await self.cost_per_action_service.get_cost_per_action(
                CostPerActionType.ASK_IAH_PLAYLIST_GENERATION
            )

            # deduct credits from user
            description = f"Ask IAH Playlist generation by {user_email} on {datetime.now(timezone.utc)} deducting {cost_per_action.cost} credits"
            await self.credit_management_service.deduct_credits(
                user_email=user_email,
                amount=cost_per_action.cost,
                api_endpoint=cost_per_action.endpoint,
                description=description,
            )

            # Emit processing event
            yield EventEmitter.processing(
                message="We are curating your playlist please wait...",
                session_id=session_id,
                message_id=message_id,
                is_processing=True,
            )

            # Get tracks with metadata
            tracks_data = await self.retrieve_tracks_with_metadata(
                user_prompt=user_prompt, k=query_type["numbers_of_tracks"]
            )

            print("tracks_data", tracks_data)

            # Extract just track IDs for compatibility
            track_ids = [track["track_id"] for track in tracks_data]
            if len(track_ids) > 0:
                track_ids_str = ", ".join(track_ids)

            # save the track ids to the database
            chat_metadata = UpdateChatMetadata(
                message_id=message_id,
                session_id=session_id,
                track_ids=track_ids_str,
                image_url=image_metadata_url,
            )

            chat_service = ChatService(session=self.session)
            await chat_service.update_chat_metadata(
                email=user_email, chat_metadata=chat_metadata
            )

            # Update metadata for playlist
            metadata.update(
                {
                    "is_playlist": True,
                    "track_ids": track_ids,
                    "numbers_of_tracks": query_type["numbers_of_tracks"],
                    "tracks_metadata": None,
                }
            )

        # Handle image generation if detected
        elif query_type["is_image"]:

            # Update API usage for playlist generation
            cost_per_action = await self.cost_per_action_service.get_cost_per_action(
                CostPerActionType.ASK_IAH_IMAGE_GENERATION
            )

            # deduct credits from user
            description = f"Ask IAH Image generation by {user_email} on {datetime.now(timezone.utc)} deducting {cost_per_action.cost} credits"
            await self.credit_management_service.deduct_credits(
                user_email=user_email,
                amount=cost_per_action.cost,
                api_endpoint=cost_per_action.endpoint,
                description=description,
            )

            yield EventEmitter.processing(
                message="Generating your image. Please wait...",
                session_id=session_id,
                message_id=message_id,
                is_processing=True,
            )

            # Generate image based on the prompt
            image_response = await self.generate_square_album_art_based_on_prompt(
                user_prompt
            )

            # save the track ids to the database
            chat_metadata = UpdateChatMetadata(
                message_id=message_id,
                session_id=session_id,
                track_ids=track_ids_str,
                image_url=image_metadata_url,
            )

            chat_service = ChatService(session=self.session)
            await chat_service.update_chat_metadata(
                email=user_email, chat_metadata=chat_metadata
            )

            # Update metadata for image
            metadata.update(
                {
                    "is_image": True,
                    "image_url": image_response["image"],
                }
            )

            # Update system prompt for image context
            system_prompt = await self._build_image_prompt(
                config, image_response["image"]
            )

        # Emit metadata event
        yield EventEmitter.metadata(metadata, session_id, message_id)

        # Build chain and get history
        chain = await self._build_chain(
            config=config,
            system_prompt=system_prompt,
            is_general_request=query_type["is_general_request"],
            is_document_related=query_type["is_upload_document_related"],
        )

        # Setup chain with message history
        chain_with_history = RunnableWithMessageHistory(
            chain,
            lambda session_id: history,
            input_messages_key="input",
            history_messages_key="chat_history",
        )

        # Process stream
        all_responses = []
        stream = chain_with_history.astream(
            {"input": config.user_prompt},
            config={
                "callbacks": [
                    CallbackHandler(
                        session_id=config.session_id,
                        user_id=config.user_email,
                        trace_name="Ask IAH Oracle",
                        metadata={"user_prompt": config.user_prompt},
                        tags=["ask-iah", "chat-with-ask-iah-oracle"],
                    )
                ],
                "configurable": {"session_id": config.session_id},
            },
        )

        async for response in stream:
            all_responses.append(response.content)
            yield EventEmitter.message(response.content, session_id, message_id)

        # Save complete chat message
        complete_output = "".join(all_responses)
        track_ids_str = ",".join(track_ids) if track_ids else None
        await self._save_chat_message(
            config=config,
            complete_output=complete_output,
            track_ids=track_ids_str,
            image_url=image_response["image"] if image_response != None else None,
        )

        # Emit completion event
        yield EventEmitter.complete(session_id, message_id)

    async def _build_image_prompt(self, config: ChatConfig, image_url: str) -> str:
        base_prompt = self.prompt_manager.load_system_prompt(
            config.concise_mode, ""  # No custom prompt for image generation
        )

        image_instructions = f"""
        You have just generated an image based on the user's request.
        The image is available at: {image_url}
        
        Please:
        1. Describe the key elements of the generated image
        2. Explain how the image relates to the user's request
        3. Point out any interesting artistic choices or details
        4. Suggest potential use cases for the image
        
        Your response should help the user understand the artistic decisions made
        and how the image fulfills their requirements.
        """

        return f"{base_prompt}\n\n{image_instructions}"
