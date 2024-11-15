from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import Response
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.siv_playlist.service import SonicIVPlaylistService
from app.auth.auth_handler import AuthHandler
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.schemas import (
    CreateSonicIVPlaylistRequest,
    SonicIVPlaylistPinnedRequest,
    UpdateSonicIVPlaylistRequest,
)

router = APIRouter()


@router.get("/user", name="Get all sonic iv playlist by user")
async def get_user_sonic_iv_playlist(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        siv_service = SonicIVPlaylistService(session)
        user_playlists = await siv_service.get_all_sonic_iv_playlist_by_user(
            email=email
        )
        payload = CommonResponse(
            message="Successfully fetch user playlists",
            success=True,
            payload=user_playlists,
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


@router.post("/create", name="Create a sonic iv playlist")
async def create_sonic_iv_playlist(
    response: Response,
    request: CreateSonicIVPlaylistRequest,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:
        sonic_iv_service = SonicIVPlaylistService(session)
        create_playlist = await sonic_iv_service.create_sonic_iv_playlist(
            email=email, playlist_data=request
        )
        payload = CommonResponse(
            message="Successfully created a sonic iv playlist",
            success=True,
            payload=create_playlist,
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


@router.get("/sonic-iv/featured", name="Get featured sonic iv playlists")
async def get_featured_sonic_iv_playlist(
    response: Response,
    session: AsyncSession = Depends(db_session),
):

    try:
        sonic_iv_service = SonicIVPlaylistService(session)
        featured_playlists = await sonic_iv_service.get_featured_sonic_iv_playlist()
        payload = CommonResponse(
            message="Successfully fetch featured sonic iv playlists",
            success=True,
            payload=featured_playlists,
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


@router.patch("/update/{playlist_id}", name="Update sonic iv playlist")
async def update_sonic_iv_playlist(
    response: Response,
    request: UpdateSonicIVPlaylistRequest,
    playlist_id: UUID4 = Path(..., title="The ID of the playlist to update"),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:
        sonic_iv_service = SonicIVPlaylistService(session)
        create_playlist = await sonic_iv_service.update_sonic_iv_playlist(
            email=email, playlist_id=playlist_id, playlist_data=request
        )
        payload = CommonResponse(
            message="Successfully updated sonic iv playlist",
            success=True,
            payload=create_playlist,
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


@router.get("/{playlist_id}", name="Get sonic iv playlist by id")
async def get_sonic_iv_playlist_by_id(
    response: Response,
    playlist_id: UUID4 = Path(...),
    session: AsyncSession = Depends(db_session),
):

    try:
        sonic_iv_service = SonicIVPlaylistService(session)
        playlist = await sonic_iv_service.get_sonic_iv_playlist_by_id(
            playlist_id=playlist_id
        )
        payload = CommonResponse(
            message="Successfully fetch sonic iv playlist",
            success=True,
            payload=playlist,
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


@router.get("/user/count", name="Get all sonic iv playlist count by user")
async def get_user_sonic_iv_playlist_count(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        sonic_iv_service = SonicIVPlaylistService(session)
        playlist_count = await sonic_iv_service.get_user_sonic_iv_playlist_count(
            email=email
        )
        payload = CommonResponse(
            message="Successfully fetch user sonic iv playlists count",
            success=True,
            payload=playlist_count,
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


@router.delete("/delete/{playlist_id}", name="Delete sonic iv playlist")
async def delete_sonic_playlist(
    response: Response,
    playlist_id: UUID4 = Path(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        sonic_iv_service = SonicIVPlaylistService(session)
        delete_playlist = await sonic_iv_service.delete_sonic_iv_playlist(
            email=email, playlist_id=playlist_id
        )
        payload = CommonResponse(
            message="Sonic IV playlist deleted successfully",
            success=True,
            payload=delete_playlist,
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


@router.patch("/pinning/{playlist_id}", name="Pinned sonic iv playlist")
async def pin_sonic_iv_playlist(
    response: Response,
    request: SonicIVPlaylistPinnedRequest,
    playlist_id: str = Path(..., title="The sonic iv playlist id"),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        sonic_iv_service = SonicIVPlaylistService(session)
        result = await sonic_iv_service.change_pin_status_of_sonic_iv_playlist(
            email=email,
            playlist_id=playlist_id,
            pinned_status=request.is_pinned,
        )
        payload = CommonResponse(
            message="The sonic iv playlist has been pinned",
            success=True,
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
        print(e)
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get("/user/pinned", name="Get all pinned sonic iv playlist by user")
async def get_user_sonic_playlist(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        sonic_iv_service = SonicIVPlaylistService(session)
        user_playlists = (
            await sonic_iv_service.get_all_pinned_sonic_iv_playlist_by_user(email=email)
        )
        payload = CommonResponse(
            message="Successfully fetch user sonic iv playlists",
            success=True,
            payload=user_playlists,
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
