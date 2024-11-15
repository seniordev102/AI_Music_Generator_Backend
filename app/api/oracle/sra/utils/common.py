import asyncio
import os
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import HTTPException, status
from langchain.prompts import load_prompt
from langchain_community.chat_message_histories import ChatMessageHistory
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import db_session
from app.logger.logger import logger
from app.models import AskIAHFileUpload, SRAChatHistory, SRAFileUpload, User
from app.schemas import CreateChatMessage
from app.ws.ws_manager import sio_server

SRA_CHAT_START = "SRA_CHAT_START"
SRA_CHAT_END = "SRA_CHAT_END"
SRA_CHAT_RESPONSE = "SRA_CHAT_RESPONSE"
SRA_CHAT_ERROR = "SRA_CHAT_ERROR"

SRA_NEW_CHAT_START = "SRA_NEW_CHAT_START"
SRA_NEW_CHAT_END = "SRA_NEW_CHAT_END"
SRA_NEW_CHAT_RESPONSE = "SRA_NEW_CHAT_RESPONSE"
SRA_NEW_CHAT_ERROR = "SRA_NEW_CHAT_ERROR"


SRA_IMAGE_GENERATION_START = "SRA_IMAGE_GENERATION_START"
SRA_IMAGE_GENERATION_END = "SRA_IMAGE_GENERATION_END"
SRA_IMAGE_GENERATION_ERROR = "SRA_IMAGE_GENERATION_ERROR"


# send start event
async def emit_websocket_event(event_name: str, data: dict, sid: str):
    try:
        await sio_server.emit(event=event_name, data=data, room=sid)
        # Allow the event loop to process the emit
        await asyncio.sleep(0)
    except Exception as e:
        logger.error(f"Error emitting event: {str(e)}")


# get chat message history by session id
async def get_chat_message_history_by_session_id(
    session_id: str,
) -> Optional[List[ChatMessageHistory]]:
    try:
        async for session in db_session():
            session: AsyncSession
            one_day_ago = datetime.now() - timedelta(days=1)

            # Adjust the query to filter chats from the last day and order by created_at descending
            chat_query = (
                select(SRAChatHistory)
                .where(SRAChatHistory.session_id == session_id)
                .where(SRAChatHistory.created_at >= one_day_ago)
                .order_by(SRAChatHistory.created_at.desc())
            )

            chat_record = await session.execute(chat_query)
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
    except Exception as e:
        logger.error(f"Error occurred while fetching chat message history: {str(e)}")
        return []


# get most recent SRA documents
async def get_most_recent_sra_document(
    session_id: str,
) -> Optional[SRAFileUpload]:
    try:
        async for session in db_session():
            session: AsyncSession
            document_records = await session.execute(
                select(SRAFileUpload)
                .where(SRAFileUpload.session_id == session_id)
                .order_by(SRAFileUpload.created_at.desc())
                .limit(1)
            )
            uploaded_document: SRAFileUpload = document_records.scalar_one_or_none()
            return uploaded_document
    except Exception as e:
        logger.debug(
            f"Error occurred while fetching most recent SRA documents: {str(e)}"
        )
        return None


# load prompt from file path
def load_prompt_from_file_path(file_path: str):
    script_path = os.path.abspath(__file__)
    script_dir = os.path.dirname(script_path)
    target_file_path = os.path.join(script_dir, file_path)
    return load_prompt(target_file_path)


# save SRA chat response to database
async def save_sra_chat_response_to_db(
    response: str,
    session_id: str,
    message_id: str,
    email: str,
):
    try:
        async for session in db_session():
            chat = CreateChatMessage(
                session_id=session_id,
                message_id=message_id,
                message=None,
                response=response,
                is_user=False,
            )

            logger.debug("Saving SRA chat message to history")
            user_record = await session.execute(select(User).where(User.email == email))

            user: User = user_record.scalar_one_or_none()

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
                )

            # first check if the chat record already exists
            chat_record = await session.execute(
                select(SRAChatHistory)
                .where(SRAChatHistory.session_id == chat.session_id)
                .where(SRAChatHistory.message_id == chat.message_id)
                .where(SRAChatHistory.is_user == False)
            )
            chat_exist: SRAChatHistory = chat_record.scalar_one_or_none()

            if chat_exist:
                for field, value in chat.dict().items():
                    if value is not None:
                        setattr(chat_exist, field, value)
                session.add(chat_exist)
                await session.commit()

            else:
                chat = SRAChatHistory(
                    user_id=user.id,
                    message_id=chat.message_id,
                    session_id=chat.session_id,
                    response=chat.response,
                    message=chat.message,
                    is_user=chat.is_user,
                )
                session.add(chat)
                await session.commit()

    except Exception as e:
        logger.error(
            f"Error occurred while saving SRA chat response to database: {str(e)}"
        )


async def get_sra_files_by_session_id(session_id: str) -> List[SRAFileUpload]:
    try:
        async for session in db_session():
            session: AsyncSession
            document_records = await session.execute(
                select(SRAFileUpload)
                .where(SRAFileUpload.session_id == session_id)
                .order_by(SRAFileUpload.created_at.desc())
            )
            return document_records.scalars().all()
    except Exception as e:
        logger.error(
            f"Error occurred while fetching most recent SRA documents: {str(e)}"
        )
        return []


async def save_generated_image_to_db(
    session_id: str, message_id: str, image_url_s3: str
):
    try:
        async for session in db_session():
            session: AsyncSession
            # get the record by session id and message id
            chat_query = (
                select(SRAChatHistory)
                .where(SRAChatHistory.session_id == session_id)
                .where(SRAChatHistory.message_id == message_id)
            )

            chat_record = await session.execute(chat_query)
            chat_history: SRAChatHistory = chat_record.scalar_one_or_none()

            # update the image url
            chat_history.image_url = image_url_s3
            await session.commit()
    except Exception as e:
        logger.error(
            f"Error occurred while saving the generated image to the database: {str(e)}"
        )


async def get_recent_generate_image_by_session_id(session_id: str):

    try:
        async for session in db_session():
            session: AsyncSession
            chat_query = (
                select(SRAChatHistory)
                .where(SRAChatHistory.session_id == session_id)
                .where(SRAChatHistory.is_user == False)
                .where(SRAChatHistory.image_url != None)
                .order_by(SRAChatHistory.created_at.desc())
            )

            chat_record = await session.execute(chat_query)
            latest_chat_record: SRAChatHistory = chat_record.scalars().first()

            if latest_chat_record:
                return latest_chat_record.image_url
            else:
                return None
    except Exception as e:
        logger.error(
            f"Error occurred while fetching the most recent generated image: {str(e)}"
        )
        return None
