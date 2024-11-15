import random

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.oracle.sonic_iv.service import SonicIVOracleService
from app.api.track.service import TrackService
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.schemas import (
    GenerateSonicIVDetails,
    GenerateSonicIVImage,
    GenerateSonicIVTracks,
)

router = APIRouter()


@router.post("/generate-tracks", name="Generate sonic iv tracks based on user prompt")
async def generate_sonic_iv_tracks(
    response: Response,
    request: GenerateSonicIVTracks = Body(...),
    session: AsyncSession = Depends(db_session),
):
    try:
        track_service = TrackService(session)
        sonic_iv_service = SonicIVOracleService(session)

        # get the track ids
        track_ids = await sonic_iv_service.retrieve_related_tracks_for_sonic_iv(
            user_prompt=request.user_prompt
        )
        tracks = await track_service.get_track_data_from_ids(track_ids)
        random.shuffle(tracks)
        payload = CommonResponse(
            message="Successfully fetched tracks for user query",
            success=True,
            payload=tracks,
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


@router.post(
    "/generate-details",
    name="Generate the title and description for the sonic iv",
)
async def generate_sonic_iv_details(
    response: Response,
    sonic_iv_details: GenerateSonicIVDetails = Body(...),
    session: AsyncSession = Depends(db_session),
):
    try:

        sonic_iv_service = SonicIVOracleService(session)
        generated_details = await sonic_iv_service.generate_sonic_iv_details(
            sonic_iv_details=sonic_iv_details
        )
        payload = CommonResponse(
            success=True,
            message="Sonic IV details generated successfully.",
            payload=generated_details,
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


@router.post(
    "/generate-images",
    name="Generate the images for the sonic iv playlist",
)
async def generate_sonic_iv_images(
    response: Response,
    user_request: GenerateSonicIVImage = Body(...),
    session: AsyncSession = Depends(db_session),
):
    try:

        sonic_iv_service = SonicIVOracleService(session)
        generated_image_details = await sonic_iv_service.generate_sonic_iv_images(
            user_prompt=user_request.user_prompt
        )
        payload = CommonResponse(
            success=True,
            message="Sonic IV image generated successfully.",
            payload=generated_image_details,
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


@router.post(
    "/generate-cover-image",
    name="Generate the cover image for the sonic iv playlist",
)
async def generate_sonic_iv_image(
    response: Response,
    user_request: GenerateSonicIVImage = Body(...),
    session: AsyncSession = Depends(db_session),
):
    try:

        sonic_iv_service = SonicIVOracleService(session)
        generated_image_details = await sonic_iv_service.generate_sonic_iv_cover_image(
            user_prompt=user_request.user_prompt
        )
        payload = CommonResponse(
            success=True,
            message="Sonic IV image generated successfully.",
            payload=generated_image_details,
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


@router.post(
    "/generate-square-image",
    name="Generate the square image for the sonic iv playlist",
)
async def generate_sonic_iv_cover_image(
    response: Response,
    user_request: GenerateSonicIVImage = Body(...),
    session: AsyncSession = Depends(db_session),
):
    try:

        sonic_iv_service = SonicIVOracleService(session)
        generated_image_details = await sonic_iv_service.generate_sonic_iv_square_image(
            user_prompt=user_request.user_prompt
        )
        payload = CommonResponse(
            success=True,
            message="Craft My Sonic image generated successfully.",
            payload=generated_image_details,
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
