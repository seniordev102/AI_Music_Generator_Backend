from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    HTTPException,
    Path,
    Query,
    status,
)
from fastapi.responses import Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.craft_my_song.service import CraftMySongService
from app.auth.auth_handler import AuthHandler
from app.common.http_response_model import CommonResponse
from app.common.logger import logger
from app.database import db_session
from app.schemas import (
    CraftMySongEditRequest,
    CraftMySongUpdateCounts,
    CreateCraftMySong,
    GenerateLyrics,
    RegenerateCoverImageRequest,
)

router = APIRouter()


@router.post("", name="Generate craft my song form user input")
async def generate_song(
    response: Response,
    background_tasks: BackgroundTasks,
    craft_my_song_request: CreateCraftMySong = Body(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:
        craft_my_song_service = CraftMySongService(session)
        result = await craft_my_song_service.generate_song_from_user_input(
            email=email,
            request_payload=craft_my_song_request,
            background_tasks=background_tasks,
        )
        payload = CommonResponse(
            success=True, message="Craft my song has been called", payload=result
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get("/{song_id}", name="Get generated track by ID")
async def get_generated_track_by_id(
    response: Response,
    song_id: str = Path(...),
    session: AsyncSession = Depends(db_session),
):
    try:
        craft_my_song_service = CraftMySongService(session)
        result = await craft_my_song_service.get_generated_track_by_id(song_id=song_id)
        payload = CommonResponse(
            success=True, message="Craft my song has been fetched", payload=result
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"HTTP error occurred while fetching craft my song: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred while fetching craft my song: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get("/user/list", name="Get generated track list by user")
async def get_generated_track_list_by_user(
    response: Response,
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=0),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:
        craft_my_song_service = CraftMySongService(session)
        result = await craft_my_song_service.get_generated_tracks_by_user(
            email=email, page=page, page_size=per_page
        )
        payload = CommonResponse(
            success=True, message="Craft my song has list fetched", payload=result
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get("/{request_id}/status", name="Get new status of the generated song")
async def request_status_update_of_generated_song(
    response: Response,
    request_id: str = Path(..., title="The request ID of the generated track"),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:
        craft_my_song_service = CraftMySongService(session)
        result = await craft_my_song_service.requesting_status_update(
            email=email, request_id=request_id
        )
        payload = CommonResponse(
            success=True, message="Craft my song has list fetched", payload=result
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.post("/generate-lyrics", name="Generate songs lyrics based on the user prompt")
async def generated_songs_lyrics(
    response: Response,
    request_payload: GenerateLyrics = Body(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:
        craft_my_song_service = CraftMySongService(session)
        lyrics = await craft_my_song_service.generate_lyrics(
            user_request=request_payload,
            user_email=email,
        )
        payload = CommonResponse(
            success=True, message="Lyrics has been generate", payload=lyrics
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"HTTP error occurred while generating user lyrics: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred while generating song lyrics: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.delete("/{song_id}", name="Delete craft my song by ID")
async def delete_song(
    response: Response,
    song_id: str = Path(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:
        craft_my_song_service = CraftMySongService(session)
        deleted = await craft_my_song_service.delete_craft_my_song_by_id(
            song_id=song_id, user_email=email
        )
        payload = CommonResponse(
            success=True, message="Song has been deleted", payload=deleted
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"Error while deleting craft my song: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred while deleting craft my song: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.patch("/{song_id}", name="Update craft my song details by ID")
async def update_song_details(
    response: Response,
    song_id: str = Path(...),
    request: CraftMySongEditRequest = Body(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:
        craft_my_song_service = CraftMySongService(session)
        updated_song = await craft_my_song_service.update_craft_my_song_details(
            song_id=song_id, user_email=email, song_data=request
        )
        payload = CommonResponse(
            success=True, message="Craft my song has been updated", payload=updated_song
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"Error while updating craft my song details: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred while updating craft my song details: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.post(
    "/{song_id}/statistic",
    name="Update craft my song play, share likes, statistic by ID",
)
async def update_song_statistics(
    response: Response,
    song_id: str = Path(...),
    request: CraftMySongUpdateCounts = Body(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:
        craft_my_song_service = CraftMySongService(session)
        updated_song = await craft_my_song_service.update_song_statistics(
            song_id=song_id, user_email=email, update_type=request.count_type
        )
        payload = CommonResponse(
            success=True,
            message="Craft my song statistic has been updated",
            payload=updated_song,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"Error while updating craft my song statistics: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred while updating craft my song statistics: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.post(
    "/{song_id}/regenerate-cover-image",
    name="Update craft my song cover image by ID",
)
async def regenerate_cong_cover_image(
    response: Response,
    song_id: str = Path(...),
    request: RegenerateCoverImageRequest = Body(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:
        craft_my_song_service = CraftMySongService(session)
        updated_song = await craft_my_song_service.update_song_cover_image(
            song_id=song_id, user_email=email, user_prompt=request.user_prompt
        )
        payload = CommonResponse(
            success=True,
            message="Craft my song cover image has been updated",
            payload=updated_song,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"Error while updating craft my song cover image: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred while updating craft my song cover image: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get(
    "/{song_id}/download",
    name="Download craft my song by ID",
)
async def download_song(
    response: Response,
    song_id: str = Path(...),
    version: int = Query(1, ge=1),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:
        craft_my_song_service = CraftMySongService(session)
        streaming_response = await craft_my_song_service.download_song(
            song_id=song_id, user_email=email, version=version
        )
        return streaming_response

    except HTTPException as http_err:
        logger.error(f"Error while downloading craft my song: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred while downloading craft my song: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload
