from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import Response
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.cms_playlist.service import CraftMySonicPlaylistService
from app.auth.auth_handler import AuthHandler
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.schemas import CreateCraftMySonicPlaylist, UpdateCraftMySonicPlaylist

router = APIRouter()


@router.get("/user", name="Get all craft my sonic playlist by user")
async def get_user_craft_my_sonic_playlist(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        cms_playlist_service = CraftMySonicPlaylistService(session)
        user_playlists = await cms_playlist_service.get_all_cms_playlist_by_user(email)
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


@router.post("/create", name="Create a craft my sonic playlist")
async def create_craft_my_sonic_playlist(
    response: Response,
    cms_playlist_data: CreateCraftMySonicPlaylist,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:
        cms_playlist_service = CraftMySonicPlaylistService(session)
        create_playlist = await cms_playlist_service.create_cms_playlist(
            email, cms_playlist_data
        )
        payload = CommonResponse(
            message="Successfully created a craft my sonic playlist",
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


@router.get("/cms/featured", name="Get featured playlists")
async def get_all_featured_playlist(
    response: Response,
    session: AsyncSession = Depends(db_session),
):

    try:
        cms_playlist_service = CraftMySonicPlaylistService(session)
        featured_playlists = await cms_playlist_service.get_featured_cms_playlist()
        payload = CommonResponse(
            message="Successfully fetch featured playlists",
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


@router.patch("/update/{playlist_id}", name="Update a craft my sonic playlist")
async def update_craft_my_sonic_playlist(
    response: Response,
    cms_playlist_data: UpdateCraftMySonicPlaylist,
    playlist_id: UUID4 = Path(..., title="The ID of the playlist to update"),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:
        cms_playlist_service = CraftMySonicPlaylistService(session)
        create_playlist = await cms_playlist_service.update_cms_playlist(
            email=email, playlist_id=playlist_id, playlist_data=cms_playlist_data
        )
        payload = CommonResponse(
            message="Successfully updated a craft my sonic playlist",
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


@router.get("/{playlist_id}", name="Get a craft my sonic playlist by id")
async def get_sonic_playlist_by_id(
    response: Response,
    playlist_id: UUID4 = Path(...),
    session: AsyncSession = Depends(db_session),
):

    try:
        cms_playlist_service = CraftMySonicPlaylistService(session)
        playlist = await cms_playlist_service.get_cms_playlist_by_id(playlist_id)
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


@router.get("/user/count", name="Get all craft my sonic playlist count by user")
async def get_user_sonic_playlist_count(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        cms_playlist_service = CraftMySonicPlaylistService(session)
        user_cms_playlists = await cms_playlist_service.get_user_cms_playlist_count(
            email
        )
        payload = CommonResponse(
            message="Successfully fetch user craft my sonic playlists count",
            success=True,
            payload=user_cms_playlists,
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


@router.delete("/delete/{playlist_id}", name="Delete a craft my sonic playlist")
async def delete_sonic_playlist(
    response: Response,
    playlist_id: UUID4 = Path(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        cms_playlist_service = CraftMySonicPlaylistService(session)
        delete_playlist = await cms_playlist_service.delete_cms_playlist(
            email, playlist_id
        )
        payload = CommonResponse(
            message="Craft my sonic playlist deleted successfully",
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
