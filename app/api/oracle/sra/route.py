import asyncio

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
from app.api.oracle.sra.service import SRAService
from app.api.oracle.sra.ws_service import SRAWebSocketService
from app.api.sra_chat.service import SRAChatService
from app.api.user.service import UserService
from app.auth.auth_handler import AuthHandler
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.schemas import (
    APIUsage,
    CreateChatMessage,
    CreateProfileImage,
    UpdateAPIUsage,
    UpdateChatMetadata,
)
from app.ws.ws_manager import sio_server

router = APIRouter()


# Unauthenticated Socket.IO event
@sio_server.on("ping")
async def custom_ping(sid, data):
    print(f"Received custom ping from {sid}: {data}")
    await sio_server.emit("pong", f"Server received: {data}", room=sid)


@sio_server.on("stream")
async def sra_art_generate_stream(sid, data):
    token = data.get("token")
    session_id = data.get("session_id")
    message_id_ai = data.get("message_id_ai")
    message_id_user = data.get("message_id_user")
    user_prompt = data.get("user_prompt")
    aspect_ratio = data.get("aspect_ratio")
    art_stye = data.get("art_stye")
    art_style_description = data.get("art_style_description")

    auth_handler = AuthHandler()
    mock_response = Response()
    try:
        email = auth_handler.verify_jwt(token, mock_response)
        if isinstance(email, CommonResponse):
            await sio_server.emit("error", {"message": email.message}, room=sid)
            return

        async for session in db_session():
            try:
                user_service = UserService(session)
                sra_chat_service = SRAChatService(session)
                sra_ws_service = SRAWebSocketService(session)

                update_key = UpdateAPIUsage(update_key=APIUsage.IAH_QUERY.value)

                # Save chat message
                chat_data = CreateChatMessage(
                    message_id=message_id_user,
                    session_id=session_id,
                    message=user_prompt,
                    response=None,
                    is_user=True,
                )

                await sra_chat_service.save_sra_chat_message(email, chat_data)
                await user_service.update_user_api_consumption(email, update_key)
                await sra_chat_service.create_sra_iah_chat_session(
                    session_id=session_id, user_email=email, user_message=user_prompt
                )

                await sra_ws_service.response_to_sra_user_query(
                    user_prompt=user_prompt,
                    aspect_ratio=aspect_ratio,
                    art_style=art_stye,
                    art_style_description=art_style_description,
                    session_id=session_id,
                    message_id=message_id_ai,
                    email=email,
                    sid=sid,
                )

            except Exception as e:
                await session.rollback()
                raise e

    except Exception as e:
        error_message = f"Stream processing failed: {str(e)}"
        await sio_server.emit("SRA_CHAT_ERROR", {"message": error_message}, room=sid)


@router.post("/stream", name="Chat with ASK IAH chat bot resonance art")
async def sra_stream(
    background_tasks: BackgroundTasks,
    body: dict = Body(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    session_id = body.get("session_id")
    message_id = body.get("message_id")
    message = body.get("user_prompt")

    sra_service = SRAService(session)

    # update the api consumption count
    user_service = UserService(session)
    sra_chat_service = SRAChatService(session)

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

    await sra_chat_service.save_sra_chat_message(email, chat_data)
    background_tasks.add_task(
        user_service.update_user_api_consumption, email, update_key
    )

    async_gen = sra_service.chat_with_sra(message, session_id, message_id, email)

    return StreamingResponse(async_gen, media_type="text/plain")


@router.post(
    "/generate-metadata",
    name="Evaluate user prompt and generate metadata for resonance art",
)
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
        aspect_ratio = body.get("aspect_ratio")
        art_style = body.get("art_style")
        art_style_description = body.get("art_style_description")

        sra_service = SRAService(session)

        # update the api consumption count
        result = await sra_service.check_image_resonance_user_prompt(
            user_prompt,
            aspect_ratio,
            art_style,
            art_style_description,
            session_id,
            message_id,
            email,
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

        sra_chat_service = SRAChatService(session)
        background_tasks.add_task(
            sra_chat_service.update_sra_chat_metadata, email, chat_metadata
        )

        payload = CommonResponse(
            success=True, message="Ask IAH chat bot response", payload=result
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
        payload = CommonResponse(
            success=False,
            message="Error while generating metadata for user prompt",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.post("/upload-docs", name="Upload documents to SRA chat bot")
async def upload_docs_to_sra_chat(
    response: Response,
    file: UploadFile = File(...),
    session_id: str = Form(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        sra_chat_service = SRAChatService(session)
        payload = await sra_chat_service.upload_docs_to_sra(
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


@router.get("/sync-sra-chat-sessions", name="Sync all sra chat sessions")
async def sync_all_chat_sessions(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        sra_chat_service = SRAChatService(session)
        await sra_chat_service.resync_all_the_sra_chat_sessions()
        payload = CommonResponse(
            success=True, message="All sra chat session has been resync", payload=True
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


@router.post(
    "/generate-profile-image", name="Generate profile image based on the user prompt"
)
async def upload_docs_to_sra_chat(
    response: Response,
    request_payload: CreateProfileImage,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        sra_service = SRAService(session)
        profile_image = await sra_service.generate_profile_image(
            user_email=email, user_prompt=request_payload.prompt
        )
        payload = CommonResponse(
            success=True, message="Profile image updated", payload=profile_image
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
            message="Error while uploading the file to ask iah chat session",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload
