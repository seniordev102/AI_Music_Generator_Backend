from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from fastapi.responses import Response
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.favorite.service import FavoriteService
from app.auth.auth_handler import AuthHandler
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.schemas import CreateFavoritePromptResponse, CreateFavoriteTrack

router = APIRouter()


@router.get("/track/user", name="Get all user favorite tracks")
async def get_user_favorite_tracks(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        favorite_service = FavoriteService(session)
        user_favorite_tracks = await favorite_service.get_all_user_favorite_tracks(
            email
        )
        payload = CommonResponse(
            message="Successfully fetch user favorite tracks",
            success=True,
            payload=user_favorite_tracks,
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


@router.get("/iah-response/user/:user_id", name="Get all user favorite iah responses")
async def get_user_favorite_iah_responses(
    response: Response, user_id: UUID4, session: AsyncSession = Depends(db_session)
):

    try:
        favorite_service = FavoriteService(session)
        user_favorite_iah_responses = (
            await favorite_service.get_all_user_favorite_iah_responses(user_id)
        )
        payload = CommonResponse(
            message="Successfully fetch user favorite iah responses",
            success=True,
            payload=user_favorite_iah_responses,
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


@router.get("/track/{track_id}", name="Get is track is favorite by user")
async def get_is_track_is_favorite(
    response: Response,
    track_id: UUID4,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        favorite_service = FavoriteService(session)
        is_track_favorite = await favorite_service.get_is_track_favorite_by_user(
            email, track_id
        )
        payload = CommonResponse(
            message="Successfully fetch user is track favorite by the user",
            success=True,
            payload=is_track_favorite,
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


@router.post("/track/add", name="Add track to favorite")
async def add_track_to_favorite(
    response: Response,
    track_favorite_data: CreateFavoriteTrack,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        favorite_service = FavoriteService(session)
        favorite_track = await favorite_service.create_favorite_track(
            track_favorite_data, email
        )
        payload = CommonResponse(
            message="Successfully added track to favorite",
            success=True,
            payload=favorite_track,
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


@router.post("/iah-response/add", name="Add iah response to favorite")
async def add_iah_response_to_favorite(
    response: Response,
    iah_response_data: CreateFavoritePromptResponse,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        favorite_service = FavoriteService(session)
        favorite_iah_response = await favorite_service.create_favorite_iah_response(
            iah_response_data, email
        )
        payload = CommonResponse(
            message="Successfully added aih response to favorite",
            success=True,
            payload=favorite_iah_response,
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


@router.delete("/track/{track_id}", name="Remove track from favorite")
async def remove_track_from_favorite(
    response: Response,
    track_id: UUID4 = Path(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        favorite_service = FavoriteService(session)
        favorite_iah_response = await favorite_service.delete_favorite_track(
            email, track_id
        )
        payload = CommonResponse(
            message="Successfully removed track from favorite",
            success=True,
            payload=favorite_iah_response,
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


@router.delete(
    "/iah-response/:iah_response_id", name="Remove iah response from favorite"
)
async def remove_iah_response_from_favorite(
    response: Response,
    iah_response_id: UUID4,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        favorite_service = FavoriteService(session)
        favorite_iah_response = await favorite_service.delete_favorite_iah_response(
            email, iah_response_id
        )
        payload = CommonResponse(
            message="Successfully removed iah response from favorite",
            success=True,
            payload=favorite_iah_response,
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
