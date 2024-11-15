import json

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import Response, StreamingResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.chat.service import ChatService
from app.api.oracle.ask_iah.events import EventEmitter
from app.api.oracle.ask_iah.opti_service import AskIahServiceOptimized
from app.api.oracle.ask_iah.service import AskIahService
from app.api.user.service import UserService
from app.auth.auth_handler import AuthHandler
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.logger.logger import logger
from app.schemas import APIUsage, CreateChatMessage, UpdateAPIUsage, UpdateChatMetadata

router = APIRouter()


@router.post("/chat-stream")
async def chat_with_ask_iah_stream(
    background_tasks: BackgroundTasks,
    body: dict = Body(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    user_prompt = body.get("user_prompt")
    session_id = body.get("session_id")
    message_id = body.get("message_id")
    message = body.get("user_prompt")
    concise_mode = body.get("concise_mode")

    ask_iah_service = AskIahServiceOptimized(session)
    chat_service = ChatService(session)

    # Save initial chat message
    chat_data = CreateChatMessage(
        message_id=message_id,
        session_id=session_id,
        message=message,
        response=None,
        is_user=True,
    )
    await chat_service.save_chat_message(email, chat_data)

    background_tasks.add_task(
        chat_service.create_iah_chat_session, session_id, email, message
    )

    async def event_generator():
        try:
            async for event in ask_iah_service.chat_with_ask_iah_oracle(
                user_prompt=user_prompt,
                session_id=session_id,
                message_id=message_id,
                user_email=email,
                concise_mode=concise_mode,
            ):
                yield f"data: {json.dumps(event.to_dict())}\n\n"
                yield ":\n\n"

        except HTTPException as e:
            logger.error(
                f"Error in Ask IAH Oracle (HTTP) ---->: {e.status_code} - {e.detail}"
            )
            if e.status_code == status.HTTP_402_PAYMENT_REQUIRED:
                error_code = "payment_required"
            else:
                error_code = "general_error"
            error_event = EventEmitter.error(
                error=str(e.detail),
                session_id=session_id,
                message_id=message_id,
                error_code=error_code,
            )
            yield f"data: {json.dumps(error_event.to_dict())}\n\n"
            yield "event: close\n\n"

        except Exception as e:
            logger.error(f"Error in Ask IAH Oracle (General) ---->: {str(e)}")
            error_code = "general_error"
            error_event = EventEmitter.error(
                error=str(e),
                session_id=session_id,
                message_id=message_id,
                error_code=error_code,
            )
            yield f"data: {json.dumps(error_event.to_dict())}\n\n"
            yield "event: close\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        },
    )


@router.post("/stream", name="Chat with ASK IAH chat bot")
async def chat_with_ask_iah_with_stream(
    background_tasks: BackgroundTasks,
    body: dict = Body(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    user_prompt = body.get("user_prompt")
    session_id = body.get("session_id")
    message_id = body.get("message_id")
    message = body.get("user_prompt")
    concise_mode = body.get("concise_mode")

    ask_iah_service = AskIahService(session)

    # update the api consumption count
    user_service = UserService(session)
    chat_service = ChatService(session)

    update_key = UpdateAPIUsage(
        update_key=APIUsage.IAH_QUERY.value,
    )

    # save chat message without waiting for the response
    chat_data = CreateChatMessage(
        message_id=message_id,
        session_id=session_id,
        message=message,
        response=None,
        is_user=True,
    )

    await chat_service.save_chat_message(email, chat_data)

    background_tasks.add_task(
        user_service.update_user_api_consumption, email, update_key
    )

    background_tasks.add_task(
        chat_service.create_iah_chat_session, session_id, email, message
    )
    async_gen = ask_iah_service.chat_with_ask_iah_oracle(
        user_prompt=user_prompt,
        session_id=session_id,
        message_id=message_id,
        user_email=email,
        concise_mode=concise_mode,
    )

    return StreamingResponse(async_gen, media_type="text/text")


@router.post("/generate-metadata", name="Evaluate user prompt and generate metadata")
async def generate_metadata_for_ask_iah(
    background_tasks: BackgroundTasks,
    response: Response,
    body: dict = Body(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        user_prompt = body.get("user_prompt")
        session_id = body.get("session_id")
        message_id = body.get("message_id")
        ask_iah_service = AskIahService(session)

        # update the api consumption count
        result = await ask_iah_service.check_user_prompt_request(
            user_prompt, session_id, message_id, email
        )

        track_ids_str = None
        if len(result["track_ids"]) > 0:
            track_ids_str = ", ".join(result["track_ids"])

        chat_metadata = UpdateChatMetadata(
            message_id=message_id,
            session_id=session_id,
            track_ids=track_ids_str,
            image_url=result["image_url"] if result["image_url"] is not None else None,
        )

        chat_service = ChatService(session)
        background_tasks.add_task(
            chat_service.update_chat_metadata, email, chat_metadata
        )

        payload = CommonResponse(
            success=True, message="Ask IAH chat bot response", payload=result
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        print(http_err)
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        print(e)
        payload = CommonResponse(
            success=False,
            message="Error while generating metadata for user prompt",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.post("/upload-docs", name="Upload documents to ASK IAH chat bot")
async def upload_docs_to_iah_chat(
    response: Response,
    file: UploadFile = File(...),
    session_id: str = Form(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        ask_iah_service = AskIahService(session)
        payload = await ask_iah_service.upload_ask_ia_docs(
            file=file, session_id=session_id, user_email=email
        )
        return True

    except HTTPException as http_err:
        print(http_err)
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        print(e)
        payload = CommonResponse(
            success=False,
            message="Error while uploading the file to ask iah chat session",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get("/sync-chat-sessions", name="Sync all chat sessions")
async def sync_all_chat_sessions(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        chat_service = ChatService(session)
        await chat_service.resync_all_the_chat_sessions()
        payload = CommonResponse(
            success=True, message="All chat session has been resync", payload=True
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
        payload = CommonResponse(
            success=False,
            message="Error while uploading the file to ask iah chat session",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload
