import logging
import os
import time
from datetime import datetime, timedelta
from io import BytesIO
from operator import itemgetter
from typing import List

import requests
from fastapi import Depends, HTTPException, status
from langchain.chains import create_structured_output_runnable
from langchain.output_parsers.openai_functions import JsonOutputFunctionsParser
from langchain.prompts import load_prompt
from langchain.schema.messages import HumanMessage
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
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.sra_chat.service import SRAChatService
from app.api.user.service import UserService
from app.common.s3_file_upload import S3FileClient
from app.database import db_session
from app.logger.logger import logger
from app.models import AskIAHFileUpload, SRAChatHistory, SRAFileUpload, User
from app.schemas import APIUsage, CreateChatMessage, UpdateAPIUsage


class SRAService:
    def __init__(self, session: AsyncSession = Depends(db_session)) -> None:
        self.session = session

    def _load_prompt_from_file_path(self, file_path: str):
        script_path = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_path)
        target_file_path = os.path.join(script_dir, file_path)
        return load_prompt(target_file_path)

    async def chat_with_sra(
        self,
        user_prompt: str,
        session_id: str,
        message_id: str,
        user_email: str,
    ):

        logger.debug("Resonance ART chat initiated")
        llm = ChatOpenAI(model="gpt-4o", temperature=0.1, streaming=True)

        loaded_prompt = self._load_prompt_from_file_path(
            "prompts/ask_iah_system_prompt.yaml"
        )
        system_prompt = loaded_prompt.template

        # check if the document data is available for session id if available retrieve the latest one
        document_records = await self.session.execute(
            select(AskIAHFileUpload)
            .where(AskIAHFileUpload.session_id == session_id)
            .order_by(AskIAHFileUpload.created_at.desc())
            .limit(1)
        )
        uploaded_document: AskIAHFileUpload = document_records.scalar_one_or_none()

        if uploaded_document:
            logger.debug("User document data is available")
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
                logger.info("User document url is available probably an image")
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
            logger.debug(
                "User document data is not available initiating chat without document data"
            )
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
        logger.debug(
            "Streaming has ended SRA. Total responses received:", len(all_responses)
        )
        complete_output = "".join(all_responses)

        chat = CreateChatMessage(
            session_id=session_id,
            message_id=message_id,
            message=None,
            response=complete_output,
            is_user=False,
        )

        logger.info("Saving SRA chat message to history")
        sra_chat_service = SRAChatService(session=self.session)
        await sra_chat_service.save_sra_chat_message(user_email, chat)

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

        prompt = self._load_prompt_from_file_path(
            "prompts/extract_metadata_prompt.yaml"
        )

        llm = ChatOpenAI(model_name="gpt-4o", temperature=0)

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
        prompt = self._load_prompt_from_file_path(
            "prompts/image_generation_prompt.yaml"
        )
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
        one_day_ago = datetime.now() - timedelta(days=1)

        # Adjust the query to filter chats from the last day and order by created_at descending
        chat_query = (
            select(SRAChatHistory)
            .where(SRAChatHistory.session_id == session_id)
            .where(SRAChatHistory.created_at >= one_day_ago)
            .order_by(SRAChatHistory.created_at.desc())
        )

        chat_record = await self.session.execute(chat_query)
        chat_history: list[SRAChatHistory] = chat_record.scalars().all()

        # Reverse the chat history to have the latest chat at the bottom
        chat_history.reverse()

        langchain_chat_history = ChatMessageHistory()
        for chat in chat_history:
            if chat.is_user:
                if chat.message:
                    langchain_chat_history.add_user_message(chat.message)
            else:
                if chat.response:
                    langchain_chat_history.add_ai_message(chat.response)
        return langchain_chat_history

    async def _get_sra_files_by_session_id(
        self, session_id: str
    ) -> List[AskIAHFileUpload]:
        document_records = await self.session.execute(
            select(AskIAHFileUpload)
            .where(AskIAHFileUpload.session_id == session_id)
            .order_by(AskIAHFileUpload.created_at.desc())
        )
        return document_records.scalars().all()

    async def analyze_image_request(
        self,
        user_prompt: str,
        aspect_ratio: str,
        art_style: str,
        art_style_description: str,
        session_id: str,
        message_id: str,
        email: str,
        sid: str,
    ) -> dict:

        try:
            llm = ChatOpenAI(model_name="gpt-4o", temperature=0)

            # get chat history for the session
            chat_history = await self.get_chat_message_history(session_id)

            sra_files = await self._get_sra_files_by_session_id(session_id)

            context = {
                "input": user_prompt,
                "chat_history": chat_history,
                "sra_files": sra_files,
                "aspect_ratio": aspect_ratio,
                "art_style": art_style,
                "art_style_description": art_style_description,
                "session_id": session_id,
                "message_id": message_id,
            }

            prompt = self._load_prompt_from_file_path(
                "prompts/sra_user_input_extract_prompt.yaml"
            )

            request_schema = {
                "name": "analyze_image_request",
                "description": "Analyze the user's image request",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "is_general_query": {
                            "type": "boolean",
                            "description": "True if the user is asking a general question not related to image generation or editing.",
                        },
                        "is_image_generation": {
                            "type": "boolean",
                            "description": "True if the user is requesting to generate a new image.",
                        },
                        "is_image_variant": {
                            "type": "boolean",
                            "description": "True if the user is requesting a variant of an uploaded image without providing specific details.",
                        },
                        "is_custom_variant": {
                            "type": "boolean",
                            "description": "True if the user is requesting a custom variant of an uploaded image with specific modifications.",
                        },
                        "is_image_edit": {
                            "type": "boolean",
                            "description": "True if the user is requesting to edit a specific portion of an uploaded image (assuming a mask layer is provided).",
                        },
                        "is_need_more_clarity": {
                            "type": "boolean",
                            "description": "True if the user's request lacks sufficient details about how the image should look.",
                        },
                        "no_of_images": {
                            "type": "integer",
                            "description": "The number of images requested by the user. Default to 1 if not specified.",
                        },
                        "context_usage": {
                            "type": "object",
                            "properties": {
                                "uses_uploaded_image": {"type": "boolean"},
                                "uses_uploaded_document": {"type": "boolean"},
                                "uses_chat_history": {"type": "boolean"},
                            },
                            "description": "Indicates whether the request makes use of uploaded images, documents, or chat history.",
                        },
                    },
                    "required": [
                        "is_general_query",
                        "is_image_generation",
                        "is_image_variant",
                        "is_custom_variant",
                        "is_image_edit",
                        "is_need_more_clarity",
                        "no_of_images",
                        "context_usage",
                    ],
                },
            }

            output_parser = JsonOutputFunctionsParser()

            chain = prompt | llm.bind(functions=[request_schema]) | output_parser

            result = await chain.ainvoke({"context": context})

            if result["is_general_query"]:
                print("General query detected, streaming response")
                await self.stream_general_query_response(
                    user_prompt, session_id, message_id, email, sid
                )
                return {"message": "General query response streamed"}

            if result["is_image_generation"] and result["is_need_more_clarity"]:
                print(
                    "Image generation request needs more clarity, asking follow-up questions"
                )
                await self.stream_image_generation_clarity_questions(
                    user_prompt, session_id, message_id, email, sid
                )
                return {"message": "Follow-up questions for image generation streamed"}

            if result["is_image_generation"]:
                print("Generating image based on user request")
                await self.generate_and_describe_image(
                    user_prompt,
                    aspect_ratio,
                    art_style,
                    art_style_description,
                    session_id,
                    message_id,
                    email,
                    sid,
                )
                return {"message": "Image generated and described"}

            return result
        except Exception as e:
            print(e)
            return {"error": str(e)}

    async def stream_general_query_response(
        self,
        user_prompt: str,
        session_id: str,
        message_id: str,
        email: str,
        sid: str,
    ):
        try:
            llm = ChatOpenAI(model="gpt-4o", temperature=0.1, streaming=True)

            loaded_prompt = self._load_prompt_from_file_path(
                "prompts/ask_iah_system_prompt.yaml"
            )
            system_prompt = loaded_prompt.template

            # check if the document data is available for session id if available retrieve the latest one
            document_records = await self.session.execute(
                select(SRAFileUpload)
                .where(SRAFileUpload.session_id == session_id)
                .order_by(SRAFileUpload.created_at.desc())
                .limit(1)
            )
            uploaded_document: SRAFileUpload = document_records.scalar_one_or_none()

            if uploaded_document:
                logger.debug("User document data is available")
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
                    logger.info("User document url is available probably an image")
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
                logger.debug(
                    "User document data is not available initiating chat without document data"
                )
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

            # After the stream ends
            logger.debug(
                "Streaming has ended SRA. Total responses received:", len(all_responses)
            )
            complete_output = "".join(all_responses)

            chat = CreateChatMessage(
                session_id=session_id,
                message_id=message_id,
                message=None,
                response=complete_output,
                is_user=False,
            )

            logger.info("Saving SRA chat message to history")
            sra_chat_service = SRAChatService(session=self.session)
            await sra_chat_service.save_sra_chat_message(email=email, chat_data=chat)

        except Exception as e:
            logger.info(f"Error while streaming SRA chat {str(e)}")

    async def stream_image_generation_clarity_questions(
        self,
        user_prompt: str,
        session_id: str,
        message_id: str,
        email: str,
        sid: str,
    ):
        try:
            llm = ChatOpenAI(model="gpt-4o", temperature=0.1, streaming=True)

            system_prompt = """You are an AI assistant specialized in helping users generate images. 
            Your task is to ask clear, specific follow-up questions to gather more details about the image 
            the user wants to generate. Focus on aspects like subject matter, style, colors, composition, 
            mood, and any specific elements they want to include or exclude. Be concise and direct in your questions."""

            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", system_prompt),
                    MessagesPlaceholder(variable_name="chat_history"),
                    ("human", "{input}"),
                ]
            )

            chain = prompt | llm

            history = await self.get_chat_message_history(session_id=session_id)
            chain_with_message_history = RunnableWithMessageHistory(
                chain,
                lambda session_id: history,
                input_messages_key="input",
                history_messages_key="chat_history",
            )

            clarity_prompt = f"I need more details about the image you want to generate. Based on your request: '{user_prompt}', I'll ask some follow-up questions to help clarify your vision."

            stream = chain_with_message_history.astream(
                {"input": clarity_prompt}, {"configurable": {"session_id": session_id}}
            )

            all_responses = []
            async for response in stream:
                all_responses.append(response.content)
            complete_output = "".join(all_responses)

            chat = CreateChatMessage(
                session_id=session_id,
                message_id=message_id,
                message=None,
                response=complete_output,
                is_user=False,
            )

            sra_chat_service = SRAChatService(session=self.session)
            await sra_chat_service.save_sra_chat_message(email=email, chat_data=chat)
        except Exception as e:
            logger.error(
                f"Error while streaming image generation clarity questions: {str(e)}"
            )

    async def generate_and_describe_image(
        self,
        user_prompt: str,
        aspect_ratio: str,
        art_style: str,
        art_style_description: str,
        session_id: str,
        message_id: str,
        email: str,
        sid: str,
    ):
        try:

            # Generate image
            image_result = await self.generate_resonance_art(
                user_prompt, aspect_ratio, art_style, art_style_description
            )
            image_url = image_result["image"]

            # Generate description
            llm = ChatOpenAI(model="gpt-4o", temperature=0.7)
            description_prompt = f"""
            Describe the following image in a concise manner (2-3 sentences):
            Image prompt: {user_prompt}
            Art style: {art_style}
            Art style description: {art_style_description}
            """
            description = await llm.apredict(description_prompt)

            # Save to chat history
            chat = CreateChatMessage(
                session_id=session_id,
                message_id=message_id,
                message=None,
                response=description,
                is_user=False,
            )
            sra_chat_service = SRAChatService(session=self.session)
            await sra_chat_service.save_sra_chat_message(email=email, chat_data=chat)

        except Exception as e:
            logger.error(f"Error while generating and describing image: {str(e)}")

    async def generate_profile_image(self, user_email: str, user_prompt: str):

        # find the user by email
        user_query = await self.session.execute(
            select(User).where(User.email == user_email)
        )
        user: User = user_query.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        IMAGE_SIZE = "1024x1024"
        llm = LangChainOpenAI(temperature=0.9)
        prompt = self._load_prompt_from_file_path(
            "prompts/profile_image_generation_prompt.yaml"
        )

        chain = RunnableParallel({"image_desc": RunnablePassthrough()}) | prompt | llm
        image_url = DallEAPIWrapper(
            model="dall-e-3",
            size=IMAGE_SIZE,
        ).run(chain.invoke(user_prompt))

        # upload the generated image to s3 bucket
        s3Client = S3FileClient()
        file_name = f"profile_{int(time.time())}.png"
        uploaded_profile_image = s3Client.upload_file_from_url_sync(
            url=image_url,
            file_name=file_name,
            folder_name="profile",
            content_type="image/png",
        )

        # update the user profile image
        user.profile_image = uploaded_profile_image
        self.session.add(user)
        await self.session.commit()

        return uploaded_profile_image
