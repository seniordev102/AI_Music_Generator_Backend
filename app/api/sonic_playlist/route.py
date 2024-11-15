from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from fastapi.responses import Response
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.sonic_playlist.service import SonicPlaylistService
from app.auth.auth_handler import AuthHandler
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.schemas import (
    ChangeSonicSupplementPinnedStatus,
    CreateSonicPlaylist,
    UpdateSonicPlaylist,
)

router = APIRouter()


@router.get("/user", name="Get all sonic playlist by user")
async def get_user_sonic_playlist(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        sonic_playlist_service = SonicPlaylistService(session)
        user_playlists = await sonic_playlist_service.get_all_playlist_by_user(email)
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


@router.post("/create", name="Create a sonic playlist")
async def create_sonic_playlist(
    response: Response,
    sonic_playlist_data: CreateSonicPlaylist,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:
        sonic_playlist_service = SonicPlaylistService(session)
        create_playlist = await sonic_playlist_service.create_sonic_playlist(
            email, sonic_playlist_data
        )
        payload = CommonResponse(
            message="Successfully created a sonic playlist",
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


@router.patch("/update/{playlist_id}", name="Update a sonic playlist")
async def create_sonic_playlist(
    response: Response,
    sonic_playlist_data: UpdateSonicPlaylist,
    playlist_id: UUID4 = Path(..., title="The ID of the playlist to update"),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:
        sonic_playlist_service = SonicPlaylistService(session)
        create_playlist = await sonic_playlist_service.update_sonic_playlist(
            email=email,
            playlist_id=playlist_id,
            playlist_data=sonic_playlist_data,
        )
        payload = CommonResponse(
            message="Successfully update a sonic playlist",
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


@router.get("/{playlist_id}", name="Get a sonic playlist by id")
async def get_sonic_playlist_by_id(
    response: Response,
    playlist_id: UUID4 = Path(...),
    session: AsyncSession = Depends(db_session),
):

    try:
        sonic_playlist_service = SonicPlaylistService(session)
        playlist = await sonic_playlist_service.get_sonic_playlist_by_id(playlist_id)
        payload = CommonResponse(
            message="Successfully fetch playlist",
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


@router.get("/user/count", name="Get all sonic playlist count by user")
async def get_user_sonic_playlist_count(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        sonic_playlist_service = SonicPlaylistService(session)
        user_sonic_playlists = (
            await sonic_playlist_service.get_user_sonic_playlist_count(email)
        )
        payload = CommonResponse(
            message="Successfully fetch user sonic playlists count",
            success=True,
            payload=user_sonic_playlists,
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


@router.delete("/delete/{playlist_id}", name="Delete a sonic playlist")
async def delete_sonic_playlist(
    response: Response,
    playlist_id: UUID4 = Path(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        sonic_playlist_service = SonicPlaylistService(session)
        delete_playlist = await sonic_playlist_service.delete_sonic_playlist(
            email, playlist_id
        )
        payload = CommonResponse(
            message="Successfully sonic deleted a playlist",
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


@router.patch("/pinning/{playlist_id}", name="Pinned the sonic supplement playlist")
async def pinned_sonic_supplement_playlist(
    response: Response,
    request: ChangeSonicSupplementPinnedStatus,
    playlist_id: str = Path(..., title="The session id of the chat history"),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        sonic_playlist_service = SonicPlaylistService(session)
        sonic_supplement = (
            await sonic_playlist_service.change_pinned_status_of_playlist(
                email=email,
                playlist_id=playlist_id,
                pinned_status=request.is_pinned,
            )
        )
        payload = CommonResponse(
            message="Sonic playlist is_pinned has been updated",
            success=True,
            payload=sonic_supplement,
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


@router.get("/user/pinned", name="Get all pinned sonic playlist by user")
async def get_user_sonic_playlist(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        sonic_playlist_service = SonicPlaylistService(session)
        user_playlists = await sonic_playlist_service.get_all_pinned_playlist_by_user(
            email
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
