from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import Response
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.playlist.service import PlaylistService
from app.auth.auth_handler import AuthHandler
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.schemas import (
    AddTrackToPlaylist,
    CopyPlaylist,
    CreatePlaylist,
    DeleteTrackFromPlaylist,
    UpdatePlaylist,
    UpdatePlaylistTracks,
)

router = APIRouter()


@router.get("/user", name="Get all playlist by user")
async def get_user_playlist(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        playlist_service = PlaylistService(session)
        user_playlists = await playlist_service.get_all_playlist_by_user(email)
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


@router.get("/{playlist_id}/public", name="Get a public playlist by id")
async def get_public_playlist_by_id(
    response: Response,
    playlist_id: UUID4 = Path(...),
    session: AsyncSession = Depends(db_session),
):

    try:
        playlist_service = PlaylistService(session)
        playlist = await playlist_service.get_public_playlist_by_id(playlist_id)
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


@router.get("/{playlist_id}", name="Get a user playlist by id")
async def get_public_playlist_by_id(
    response: Response,
    email: str = Depends(AuthHandler()),
    playlist_id: UUID4 = Path(...),
    session: AsyncSession = Depends(db_session),
):

    try:
        playlist_service = PlaylistService(session)
        playlist = await playlist_service.get_user_playlist_by_id(
            user_email=email, playlist_id=playlist_id
        )
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


@router.get("/user/count", name="Get all playlist count by user")
async def get_user_playlist_count(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        playlist_service = PlaylistService(session)
        user_playlists = await playlist_service.get_user_playlist_count(email)
        payload = CommonResponse(
            message="Successfully fetch user playlists count",
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


@router.post("/create", name="Create a playlist")
async def create_playlist(
    response: Response,
    playlist_data: CreatePlaylist,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        playlist_service = PlaylistService(session)
        create_playlist = await playlist_service.create_playlist(email, playlist_data)
        payload = CommonResponse(
            message="Successfully created a playlist",
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


@router.post("/{playlist_id}/copy", name="Copy existing playlist to current user")
async def copy_playlist(
    response: Response,
    copy_playlist_request: CopyPlaylist,
    playlist_id: UUID4 = Path(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        playlist_service = PlaylistService(session)
        create_playlist = await playlist_service.copy_playlist(
            user_email=email,
            playlist_id=playlist_id,
            playlist_data=copy_playlist_request,
        )
        payload = CommonResponse(
            message="Successfully copy playlist to the user",
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


@router.patch("/update/{playlist_id}", name="Update a playlist")
async def update_playlist(
    response: Response,
    playlist_data: UpdatePlaylist,
    playlist_id: UUID4 = Path(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        playlist_service = PlaylistService(session)
        create_playlist = await playlist_service.update_playlist(
            email, playlist_data, playlist_id
        )
        payload = CommonResponse(
            message="Successfully created a playlist",
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


@router.patch("/update/tracks/{playlist_id}", name="Update a playlist")
async def update_playlist(
    response: Response,
    playlist_tracks: UpdatePlaylistTracks,
    playlist_id: UUID4 = Path(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        playlist_service = PlaylistService(session)
        create_playlist = await playlist_service.update_playlist_tracks(
            email, playlist_tracks, playlist_id
        )
        payload = CommonResponse(
            message="Successfully created a playlist",
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


@router.patch("/delete-track", name="Delete a track from playlist")
async def delete_track_from_playlist(
    response: Response,
    delete_track_data: DeleteTrackFromPlaylist,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        playlist_service = PlaylistService(session)
        updated_playlist = await playlist_service.delete_track_from_playlist(
            email, delete_track_data
        )
        payload = CommonResponse(
            message="Successfully remove the track from playlist",
            success=True,
            payload=updated_playlist,
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


@router.patch("/add-track", name="Add a track to a playlist")
async def add_new_track_to_playlist(
    response: Response,
    add_new_track_data: AddTrackToPlaylist,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        playlist_service = PlaylistService(session)
        updated_playlist = await playlist_service.add_new_track_to_playlist(
            email, add_new_track_data
        )
        payload = CommonResponse(
            message="Successfully added new track to playlist",
            success=True,
            payload=updated_playlist,
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


@router.delete("/delete/{playlist_id}", name="Delete a playlist")
async def delete_playlist(
    response: Response,
    playlist_id: UUID4 = Path(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        playlist_service = PlaylistService(session)
        delete_playlist = await playlist_service.delete_playlist(email, playlist_id)
        payload = CommonResponse(
            message="Successfully deleted a playlist",
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
