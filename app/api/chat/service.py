import math
from datetime import datetime, timedelta
from typing import List

from fastapi import Depends, HTTPException, status
from pydantic import UUID4
from sqlalchemy import and_, asc, delete, desc, distinct, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.http_response_model import PageMeta
from app.database import db_session
from app.logger.logger import logger
from app.models import ChatHistory, IAHChatSession, SRAChatHistory, User
from app.schemas import CreateChatMessage, UpdateChatMetadata


class ChatService:
    def __init__(
        self,
        session: AsyncSession = Depends(db_session),
    ) -> None:
        self.session = session

    async def save_chat_message(
        self, email: str, chat_data: CreateChatMessage
    ) -> ChatHistory:

        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # first check if the chat record already exists
        chat_record = await self.session.execute(
            select(ChatHistory)
            .where(ChatHistory.session_id == chat_data.session_id)
            .where(ChatHistory.message_id == chat_data.message_id)
            .where(ChatHistory.is_user == False)
        )
        chat: ChatHistory = chat_record.scalar_one_or_none()

        if chat:
            for field, value in chat_data.dict().items():
                if value is not None:
                    setattr(chat, field, value)
            self.session.add(chat)
            await self.session.commit()

        else:
            chat = ChatHistory(
                user_id=user.id,
                message_id=chat_data.message_id,
                session_id=chat_data.session_id,
                response=chat_data.response,
                message=chat_data.message,
                is_user=chat_data.is_user,
            )
            self.session.add(chat)
            await self.session.commit()

        return chat

    async def save_sra_chat_message(
        self, email: str, chat_data: CreateChatMessage
    ) -> SRAChatHistory:

        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # first check if the chat record already exists
        chat_record = await self.session.execute(
            select(SRAChatHistory)
            .where(SRAChatHistory.session_id == chat_data.session_id)
            .where(SRAChatHistory.message_id == chat_data.message_id)
            .where(SRAChatHistory.is_user == False)
        )
        chat: SRAChatHistory = chat_record.scalar_one_or_none()

        if chat:
            for field, value in chat_data.dict().items():
                if value is not None:
                    setattr(chat, field, value)
            self.session.add(chat)
            await self.session.commit()

        else:
            chat = SRAChatHistory(
                user_id=user.id,
                message_id=chat_data.message_id,
                session_id=chat_data.session_id,
                response=chat_data.response,
                message=chat_data.message,
                is_user=chat_data.is_user,
            )
            self.session.add(chat)
            await self.session.commit()

        return chat

    async def update_chat_metadata(
        self, email: str, chat_metadata: UpdateChatMetadata
    ) -> ChatHistory:

        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # get the chat record base on session_id and message_id
        chat_record = await self.session.execute(
            select(ChatHistory)
            .where(ChatHistory.session_id == chat_metadata.session_id)
            .where(ChatHistory.message_id == chat_metadata.message_id)
            .where(ChatHistory.is_user == False)
        )
        chat: ChatHistory = chat_record.scalar_one_or_none()

        if chat:
            for field, value in chat_metadata.dict().items():
                if value is not None:
                    setattr(chat, field, value)
            self.session.add(chat)
            await self.session.commit()
        else:
            # save the chat record
            chat = ChatHistory(
                user_id=user.id,
                message_id=chat_metadata.message_id,
                session_id=chat_metadata.session_id,
                image_url=chat_metadata.image_url,
                track_ids=chat_metadata.track_ids,
                is_user=False,
            )
            self.session.add(chat)
            await self.session.commit()

        return chat

    async def update_sra_chat_metadata(
        self, email: str, chat_metadata: UpdateChatMetadata
    ) -> SRAChatHistory:

        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # get the chat record base on session_id and message_id
        chat_record = await self.session.execute(
            select(SRAChatHistory)
            .where(SRAChatHistory.session_id == chat_metadata.session_id)
            .where(SRAChatHistory.message_id == chat_metadata.message_id)
            .where(SRAChatHistory.is_user == False)
        )
        chat: SRAChatHistory = chat_record.scalar_one_or_none()

        if chat:
            for field, value in chat_metadata.dict().items():
                if value is not None:
                    setattr(chat, field, value)
            self.session.add(chat)
            await self.session.commit()
        else:
            # save the chat record
            chat = SRAChatHistory(
                user_id=user.id,
                message_id=chat_metadata.message_id,
                session_id=chat_metadata.session_id,
                image_url=chat_metadata.image_url,
                track_ids=chat_metadata.track_ids,
                is_user=False,
            )
            self.session.add(chat)
            await self.session.commit()

        return chat

    async def get_user_chat_sessions(self, email: str, limit: int):

        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        chat_query = (
            select(ChatHistory.session_id, ChatHistory.message, ChatHistory.created_at)
            .where(ChatHistory.user_id == user.id, ChatHistory.is_user == True)
            .distinct(ChatHistory.session_id)
            .limit(limit)
        )
        chat_record = await self.session.execute(chat_query)
        chat_sessions: List[ChatHistory] = chat_record.fetchall()

        # chat_sessions = chat_sessions[::-1]

        # Construct the result
        result = [
            {
                "session_id": str(session.session_id),
                "title": session.message or "No message available",
            }
            for session in chat_sessions
        ]

        return result

    async def get_user_chat_history_by_session(self, email: str, session_id: UUID4):

        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        chat_query = (
            select(ChatHistory)
            .where(ChatHistory.user_id == user.id)
            .where(ChatHistory.session_id == session_id)
            .order_by(asc(ChatHistory.created_at))
        )
        chat_record = await self.session.execute(chat_query)
        chat_history = chat_record.scalars().all()

        return chat_history

    def get_start_of_day(self, reference_date: datetime):
        return reference_date.replace(hour=0, minute=0, second=0, microsecond=0)

    async def get_sessions_by_date_range(
        self, user_id: UUID4, start_date, end_date=None
    ):
        if end_date is None:
            end_date = start_date + timedelta(
                days=1
            )  # Defaults to one day range if no end_date provided

        subquery = (
            select(
                ChatHistory.session_id, func.max(ChatHistory.created_at).label("latest")
            )
            .where(
                and_(
                    ChatHistory.user_id == user_id,
                    ChatHistory.is_user == True,
                    ChatHistory.created_at >= start_date,
                    ChatHistory.created_at < end_date,
                )
            )
            .group_by(ChatHistory.session_id)
            .alias("subquery")
        )

        final_query = (
            select(ChatHistory.session_id, ChatHistory.message, ChatHistory.created_at)
            .join(
                subquery,
                and_(
                    ChatHistory.session_id == subquery.c.session_id,
                    ChatHistory.created_at == subquery.c.latest,
                ),
            )
            .order_by(desc(ChatHistory.created_at))
        )

        chat_record = await self.session.execute(final_query)
        return chat_record.scalars().all()

    async def get_user_chat_sessions_by_date_range(
        self,
        email: str,
    ):
        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        today_start = self.get_start_of_day(datetime.now())
        yesterday_start = today_start - timedelta(days=1)
        seven_days_ago = today_start - timedelta(days=7)
        thirty_days_ago = today_start - timedelta(days=30)

        sessions_today = await self.get_sessions_by_date_range(
            user_id=user.id, start_date=today_start
        )
        sessions_yesterday = await self.get_sessions_by_date_range(
            user_id=user.id, start_date=yesterday_start
        )
        sessions_seven_days = await self.get_sessions_by_date_range(
            user_id=user.id, start_date=seven_days_ago
        )
        sessions_thirty_days = await self.get_sessions_by_date_range(
            user_id=user.id, start_date=thirty_days_ago
        )

        today_sessions_with_messages = []
        yesterday_sessions_with_messages = []
        seven_days_sessions_with_messages = []
        thirty_days_sessions_with_messages = []

        if len(sessions_today) > 0:
            for session_id in sessions_today:
                first_message = await self.get_first_user_message_by_session(session_id)
                session_payload = {
                    "session_id": str(session_id),
                    "message": first_message,
                }
                today_sessions_with_messages.append(session_payload)

        if len(sessions_yesterday) > 0:
            for session_id in sessions_yesterday:
                first_message = await self.get_first_user_message_by_session(session_id)
                session_payload = {
                    "session_id": str(session_id),
                    "message": first_message,
                }
                yesterday_sessions_with_messages.append(session_payload)

        if len(sessions_seven_days) > 0:
            for session_id in sessions_seven_days:
                first_message = await self.get_first_user_message_by_session(session_id)
                session_payload = {
                    "session_id": str(session_id),
                    "message": first_message,
                }
                seven_days_sessions_with_messages.append(session_payload)

        if len(sessions_thirty_days) > 0:
            for session_id in sessions_thirty_days:
                first_message = await self.get_first_user_message_by_session(session_id)
                session_payload = {
                    "session_id": str(session_id),
                    "message": first_message,
                }
                thirty_days_sessions_with_messages.append(session_payload)

        result = {
            "today": today_sessions_with_messages,
            "yesterday": yesterday_sessions_with_messages,
            "seven_days": seven_days_sessions_with_messages,
            "thirty_days": thirty_days_sessions_with_messages,
        }

        return result

    async def get_first_user_message_by_session(self, session_id: UUID4):
        chat_query = (
            select(ChatHistory.message)
            .where(ChatHistory.session_id == session_id)
            .where(ChatHistory.is_user == True)
            .order_by(ChatHistory.created_at.asc())
            .limit(1)
        )
        chat_record = await self.session.execute(chat_query)
        chat_history = chat_record.scalar_one_or_none()

        return chat_history

    async def delete_session_by_session_id(self, session_id: UUID4):
        chat_query = select(ChatHistory).where(ChatHistory.session_id == session_id)
        chat_record = await self.session.execute(chat_query)
        chat_history = chat_record.scalars().all()

        for chat in chat_history:
            await self.session.delete(chat)
        await self.session.commit()

        # then delete the chat session table
        session_delete = delete(IAHChatSession).where(
            IAHChatSession.session_id == session_id
        )
        await self.session.execute(session_delete)
        await self.session.commit()

        return True

    async def create_iah_chat_session(
        self, session_id: str, user_email: str, user_message: str
    ) -> None:

        # get the user by user email
        user_record = await self.session.execute(
            select(User).where(User.email == user_email)
        )

        user: User = user_record.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        chat_session_query = (
            select(IAHChatSession)
            .where(IAHChatSession.session_id == session_id)
            .where(IAHChatSession.user_id == user.id)
        )
        chat_session_record = await self.session.execute(chat_session_query)
        chat_record = chat_session_record.scalar_one_or_none()

        iah_session = IAHChatSession(
            session_id=session_id,
            user_id=user.id,
            title=user_message,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        if chat_record is None:
            # save new record into the database
            self.session.add(iah_session)
            await self.session.commit()
            logger.debug(f"session id {iah_session.session_id} saved in the database")
        else:
            chat_record.updated_at = datetime.now()
            await self.session.commit()
            logger.debug(
                f"session id {iah_session.session_id} already found skipping saving"
            )

    async def update_session_title(
        self, session_id: str, user_email: str, title: str
    ) -> None:

        user_record = await self.session.execute(
            select(User).where(User.email == user_email)
        )

        user: User = user_record.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        chat_session_query = (
            select(IAHChatSession)
            .where(IAHChatSession.session_id == session_id)
            .where(IAHChatSession.user_id == user.id)
        )

        chat_session_record = await self.session.execute(chat_session_query)
        chat_record: IAHChatSession = await chat_session_record.scalar_one_or_none()

        if chat_record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User session not found"
            )
        else:
            chat_record.title = title
            self.session(chat_record)
            await self.session.commit()

    async def resync_all_the_chat_sessions(self) -> None:

        # get all the unique sessions
        unique_session_query = await self.session.execute(
            select(distinct(ChatHistory.session_id))
        )
        unique_sessions = unique_session_query.scalars().all()

        for session_id in unique_sessions:

            # get the first message of each session
            fist_chat_query = (
                select(ChatHistory)
                .where(ChatHistory.session_id == session_id)
                .where(ChatHistory.is_user == True)
                .order_by(ChatHistory.created_at.asc())
                .limit(1)
            )
            first_chat_record = await self.session.execute(fist_chat_query)
            first_chat_history: ChatHistory = first_chat_record.scalar_one_or_none()

            if first_chat_history is not None:
                # check chat session record
                chat_session_query = (
                    select(IAHChatSession)
                    .where(IAHChatSession.session_id == session_id)
                    .where(IAHChatSession.user_id == first_chat_history.user_id)
                )
                chat_session_record = await self.session.execute(chat_session_query)
                chat_session = chat_session_record.scalar_one_or_none()

                if chat_session is None:
                    logger.debug(f"syncing new chat record for session id {session_id}")
                    new_session_record = IAHChatSession(
                        session_id=session_id,
                        user_id=first_chat_history.user_id,
                        title=first_chat_history.message,
                        created_at=first_chat_history.created_at,
                        updated_at=first_chat_history.updated_at,
                    )
                    self.session.add(new_session_record)
                    await self.session.commit()
                else:
                    logger.debug(
                        f"chat session found for session id: {session_id} skipping syncing"
                    )
            else:
                logger.debug("resync skipping chat user message not found")

    async def get_user_chat_session_history(
        self, user_email: str, page: int, page_size: int
    ):
        # get the user details by user email
        user_record = await self.session.execute(
            select(User).where(User.email == user_email)
        )

        user: User = user_record.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        chat_sessions_query = (
            select(IAHChatSession)
            .where(IAHChatSession.user_id == user.id)
            .where(IAHChatSession.is_pinned == False)
            .order_by(IAHChatSession.updated_at.desc())
        )

        # Count total sessions
        count_query = select(func.count()).select_from(chat_sessions_query.subquery())
        total_sessions = await self.session.scalar(count_query)

        # Pagination
        total_pages = max(1, math.ceil(total_sessions / page_size))
        current_page = max(1, min(page, total_pages))
        offset = (current_page - 1) * page_size

        # Fetch paginated results
        paginated_query = chat_sessions_query.offset(offset).limit(page_size)
        result = await self.session.execute(paginated_query)
        sessions = result.scalars().all()

        pagination = PageMeta(
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            total_items=total_sessions,
        )

        return sessions, pagination

    async def get_user_pinned_chat_session_history(
        self, user_email: str, page: int, page_size: int
    ):
        # get the user details by user email
        user_record = await self.session.execute(
            select(User).where(User.email == user_email)
        )

        user: User = user_record.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        chat_sessions_query = (
            select(IAHChatSession)
            .where(IAHChatSession.user_id == user.id)
            .where(IAHChatSession.is_pinned == True)
            .order_by(IAHChatSession.updated_at.desc())
        )

        # Count total sessions
        count_query = select(func.count()).select_from(chat_sessions_query.subquery())
        total_sessions = await self.session.scalar(count_query)

        # Pagination
        total_pages = max(1, math.ceil(total_sessions / page_size))
        current_page = max(1, min(page, total_pages))
        offset = (current_page - 1) * page_size

        # Fetch paginated results
        paginated_query = chat_sessions_query.offset(offset).limit(page_size)
        result = await self.session.execute(paginated_query)
        sessions = result.scalars().all()

        pagination = PageMeta(
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            total_items=total_sessions,
        )

        return sessions, pagination

    async def change_the_chat_session_title(
        self, user_email: str, session_id: str, new_title: str
    ) -> IAHChatSession:
        # get the user details by user email
        user_record = await self.session.execute(
            select(User).where(User.email == user_email)
        )

        user: User = user_record.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # get the session record
        session_record = await self.session.execute(
            select(IAHChatSession)
            .where(IAHChatSession.session_id == session_id)
            .where(IAHChatSession.user_id == user.id)
        )

        chat_session: IAHChatSession = session_record.scalar_one_or_none()
        if chat_session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found for given id and user",
            )

        query = text(
            """
            UPDATE iah_chat_sessions
            SET title = :title
            WHERE id = :id
            """
        )

        await self.session.execute(
            query,
            {
                "title": new_title,
                "id": chat_session.id,
            },
        )

        await self.session.commit()

        # Refresh the chat_session object to get the updated data
        await self.session.refresh(chat_session)

        return chat_session

    async def change_the_chat_session_is_pinned(
        self, user_email: str, session_id: str, is_pinned: bool
    ) -> IAHChatSession:
        # get the user details by user email
        user_record = await self.session.execute(
            select(User).where(User.email == user_email)
        )

        user: User = user_record.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # get the session record
        session_record = await self.session.execute(
            select(IAHChatSession)
            .where(IAHChatSession.session_id == session_id)
            .where(IAHChatSession.user_id == user.id)
        )

        chat_session: IAHChatSession = session_record.scalar_one_or_none()
        if chat_session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found for given id and user",
            )

        query = text(
            """
            UPDATE iah_chat_sessions
            SET is_pinned = :is_pinned, pinned_at = :pinned_at
            WHERE id = :id
            """
        )

        await self.session.execute(
            query,
            {
                "is_pinned": is_pinned,
                "pinned_at": datetime.now(),
                "id": chat_session.id,
            },
        )
        await self.session.commit()

        # Refresh the chat_session object to get the updated data
        await self.session.refresh(chat_session)

        return chat_session
