from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from fastapi.responses import Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.chat.service import ChatService
from app.auth.auth_handler import AuthHandler
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.schemas import ChangeChatSessionIsPinned, ChangeChatSessionTitle

router = APIRouter()


@router.get("/user", name="Get the user chat sessions")
async def get_user_chat_history(
    response: Response,
    limit: int = 10,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        chat_service = ChatService(session)
        chat_history = await chat_service.get_user_chat_sessions_by_date_range(email)
        payload = CommonResponse(
            message="Successfully fetch user sessions",
            success=True,
            payload=chat_history,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        print(e)
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get(
    "/user/history/{session_id}", name="Get the user chat history by session id"
)
async def get_user_chat_history(
    response: Response,
    email: str = Depends(AuthHandler()),
    session_id: str = Path(..., title="The session id of the chat history"),
    session: AsyncSession = Depends(db_session),
):

    try:
        chat_service = ChatService(session)
        chat_history = await chat_service.get_user_chat_history_by_session(
            email, session_id
        )
        payload = CommonResponse(
            message="Successfully fetch user chat history",
            success=True,
            payload=chat_history,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.delete("/user/history/{session_id}", name="Delete chat history by session id")
async def delete_chat_history_by(
    response: Response,
    email: str = Depends(AuthHandler()),
    session_id: str = Path(..., title="The session id of the chat history"),
    session: AsyncSession = Depends(db_session),
):

    try:
        chat_service = ChatService(session)
        chat_history = await chat_service.delete_session_by_session_id(session_id)
        payload = CommonResponse(
            message="Successfully delete chat history",
            success=True,
            payload=chat_history,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get("/chat-history", name="Get user chat session history by user")
async def get_user_chat_history(
    response: Response,
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=0),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        chat_service = ChatService(session)
        sessions, pagination = await chat_service.get_user_chat_session_history(
            user_email=email, page=page, page_size=per_page
        )
        payload = CommonResponse(
            message="Successfully fetch user sessions",
            success=True,
            payload=sessions,
            meta=pagination,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        print(e)
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get("/pinned/chat-history", name="Get user chat session history by user")
async def get_user_pinned_chat_history(
    response: Response,
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=0),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        chat_service = ChatService(session)
        sessions, pagination = await chat_service.get_user_pinned_chat_session_history(
            user_email=email, page=page, page_size=per_page
        )
        payload = CommonResponse(
            message="Successfully fetch user sessions",
            success=True,
            payload=sessions,
            meta=pagination,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        print(e)
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.patch("/change-title/{session_id}", name="Change the title of session")
async def get_user_chat_history(
    response: Response,
    request_payload: ChangeChatSessionTitle,
    session_id: str = Path(..., title="The session id of the chat history"),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        chat_service = ChatService(session)
        chat_session = await chat_service.change_the_chat_session_title(
            user_email=email, session_id=session_id, new_title=request_payload.title
        )
        payload = CommonResponse(
            message="Session title has been updated",
            success=True,
            payload=chat_session,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        print(e)
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.patch("/pinning/{session_id}", name="Change the title of session")
async def change_chat_session_pinned(
    response: Response,
    request_payload: ChangeChatSessionIsPinned,
    session_id: str = Path(..., title="The session id of the chat history"),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        chat_service = ChatService(session)
        chat_session = await chat_service.change_the_chat_session_is_pinned(
            user_email=email, session_id=session_id, is_pinned=request_payload.is_pinned
        )
        payload = CommonResponse(
            message="Session is_pinned has been updated",
            success=True,
            payload=chat_session,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        print(e)
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload
