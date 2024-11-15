import json
from datetime import datetime as dt
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.sql.schema import MetaData
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.chat.service import ChatService
from app.api.oracle.ask_iah.route import router as ask_iah_router
from app.api.oracle.craft_my_sonic.route import router as craft_my_sonic_router
from app.api.oracle.ingress.route import router as ingress_router
from app.api.oracle.service import OracleService
from app.api.oracle.sonic_iv.route import router as sonic_iv_router
from app.api.oracle.sonic_supplement.route import router as ss_router
from app.api.oracle.sra.route import router as sra_router
from app.api.oracle.summarize.route import router as summarize_router
from app.api.oracle.tts.route import router as tts_router
from app.api.oracle.user_prompt.route import router as user_prompt_router
from app.api.user.service import UserService
from app.auth.auth_handler import AuthHandler
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.models import Collection, Track
from app.schemas import APIUsage, CreateChatMessage, UpdateAPIUsage, UpdateChatMetadata

router = APIRouter()
router.include_router(ask_iah_router, prefix="/ask-iah", tags=["ask_iah"])
router.include_router(ss_router, prefix="/sonic-playlist", tags=["sonic_playlist"])
router.include_router(summarize_router, prefix="/summarize", tags=["summarize"])
router.include_router(
    craft_my_sonic_router, prefix="/craft-my-sonic", tags=["craft-my-sonic"]
)

router.include_router(ingress_router, prefix="/ingress", tags=["ingress"])
router.include_router(sra_router, prefix="/sra", tags=["sra"])
router.include_router(tts_router, prefix="/tts", tags=["text-to-speech"])
router.include_router(
    user_prompt_router, prefix="/custom-prompt", tags=["user-custom-prompt"]
)
router.include_router(sonic_iv_router, prefix="/sonic-iv", tags=["sonic-iv"])


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, dt):
            return obj.isoformat()
        elif isinstance(obj, UUID):
            return str(obj)
        elif isinstance(obj, MetaData):
            # If you don't need to serialize MetaData, you can just skip it or return a placeholder
            return "MetaData object"  # Or return None, or some other placeholder value
        elif isinstance(obj, (Collection, Track)):
            # Convert Collection and Track objects to dictionaries
            # Adjust this according to the structure of your Collection and Track objects
            return {
                attr: getattr(obj, attr)
                for attr in dir(obj)
                if not attr.startswith("_") and not callable(getattr(obj, attr))
            }
        return json.JSONEncoder.default(self, obj)


@router.get("/data-dump", name="Get all tracks with collection details")
async def get_tracks_belongs_to_album(
    response: Response, session: AsyncSession = Depends(db_session)
):
    try:
        oracle_service = OracleService(session)
        collections = await oracle_service.get_all_collections()

        #  get all tracks of an album
        tracks = await oracle_service.get_all_tracks()

        payload_data = {"collections": collections, "tracks": tracks}

        filename = "payload_data.json"

        # Write data to a JSON file
        with open(filename, "w") as file:
            json.dump(payload_data, file, cls=CustomEncoder, indent=4)

        payload = CommonResponse(
            success=True,
            message="Collection and tracks details fetched successfully",
            payload=payload_data,
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
            success=False, message="Error creating album", payload=str(e)
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get("/indexing-data", name="Get all track details with collection details")
async def get_all_indexing_data(
    response: Response, session: AsyncSession = Depends(db_session)
):
    try:
        oracle_service = OracleService(session)
        data_list = await oracle_service.get_all_data_for_indexing()

        payload = CommonResponse(
            success=True,
            message="All track details has been fetched successful",
            payload=data_list[0],
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
            success=False, message="Error while fetching track details", payload=str(e)
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get("/sync-ai", name="Get all track details with collection details")
async def sync_ai_metadata(
    response: Response,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(db_session),
):
    try:
        oracle_service = OracleService(session)
        result = await oracle_service.sync_all_ai_metadata_for_tracks(background_tasks)

        payload = CommonResponse(
            success=True,
            message="All track details has been fetched successful",
            payload=result,
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
            success=False, message="Error while fetching track details", payload=str(e)
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get("/question", name="Index tracks data into the vector database")
async def sync_ai_metadata(
    response: Response, session: AsyncSession = Depends(db_session)
):
    try:
        oracle_service = OracleService(session)
        result = await oracle_service.generate_relevant_tracks()

        payload = CommonResponse(
            success=True,
            message="All track details has been fetched successful",
            payload=result,
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
            success=False, message="Error while fetching track details", payload=str(e)
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.post("/chat", name="Chat with ASK IAH chat bot")
async def chat_with_ask_iah(
    response: Response,
    body: dict = Body(...),
    session: AsyncSession = Depends(db_session),
):
    try:
        user_prompt = body.get("user_prompt")
        session_id = body.get("session_id")
        oracle_service = OracleService(session)
        result = await oracle_service.chat_with_ask_iah_oracle(user_prompt, session_id)

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
        payload = CommonResponse(
            success=False,
            message="Error while retrieving chat bot response",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.post("/chat-stream", name="Chat with ASK IAH chat bot")
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

    oracle_service = OracleService(session)

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

    async_gen = oracle_service.chat_with_ask_iah_oracle(
        user_prompt, session_id, message_id, email
    )

    return StreamingResponse(async_gen, media_type="text/plain")


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
        oracle_service = OracleService(session)

        # update the api consumption count
        result = await oracle_service.check_user_prompt_request(
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


@router.post(
    "/chat-stream-resonance-art", name="Chat with ASK IAH chat bot resonance art"
)
async def chat_with_ask_iah_sra_with_stream(
    background_tasks: BackgroundTasks,
    body: dict = Body(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    user_prompt = body.get("user_prompt")
    session_id = body.get("session_id")
    message_id = body.get("message_id")
    message = body.get("user_prompt")

    oracle_service = OracleService(session)

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

    await chat_service.save_sra_chat_message(email, chat_data)
    background_tasks.add_task(
        user_service.update_user_api_consumption, email, update_key
    )

    async_gen = oracle_service.chat_with_ask_iah_oracle(
        user_prompt, session_id, message_id, email
    )

    return StreamingResponse(async_gen, media_type="text/plain")


@router.post(
    "/generate-metadata-resonance-art",
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

        oracle_service = OracleService(session)

        # update the api consumption count
        result = await oracle_service.check_image_resonance_user_prompt(
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

        chat_service = ChatService(session)
        background_tasks.add_task(
            chat_service.update_sra_chat_metadata, email, chat_metadata
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


@router.get("/re-sync-track-ai-metadata", name="Resync all track AI metadata details")
async def resync_track_ai_metadata(
    response: Response,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(db_session),
):
    try:
        oracle_service = OracleService(session)
        result = await oracle_service.reindex_all_metadata_for_tracks(background_tasks)

        payload = CommonResponse(
            success=True,
            message="All track details has been fetched successful",
            payload=result,
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
            success=False, message="Error while fetching track details", payload=str(e)
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.post(
    "/retrieve-collections",
    name="Retrieve most relevant collections based on user prompt",
)
async def generate_metadata_for_ask_iah(
    response: Response,
    body: dict = Body(...),
    session: AsyncSession = Depends(db_session),
):

    try:
        user_prompt = body.get("user_prompt")
        oracle_service = OracleService(session)
        result = await oracle_service.retrieve_related_collection_based_on_prompt(
            user_prompt
        )

        payload = CommonResponse(
            success=True,
            message="Related collections based on user prompt",
            payload=result,
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
            message="Error while retrieving related collections based on user prompt",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.post(
    "/get-related-tracks", name="Retrieve most relevant tracks based on user prompt"
)
async def get_related_tracks_based_on_prompt(
    response: Response,
    body: dict = Body(...),
    session: AsyncSession = Depends(db_session),
):

    try:
        user_prompt = body.get("user_prompt")
        oracle_service = OracleService(session)
        result = await oracle_service.retrieve_related_tracks_based_on_prompt(
            user_prompt
        )

        payload = CommonResponse(
            success=True, message="Related tracks based on user prompt", payload=result
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
            message="Error while retrieving related tracks based on user prompt",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload
