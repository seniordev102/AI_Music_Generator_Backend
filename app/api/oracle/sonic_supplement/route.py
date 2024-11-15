from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import Response, StreamingResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.oracle.sonic_supplement.service import SSOracleService
from app.auth.auth_handler import AuthHandler
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.schemas import SSGenerativeRequest

router = APIRouter()


@router.post(
    "/generate-details",
    name="Generate title and description based on the sonic supplement track selection",
)
async def generate_title_based_on_tracks(
    response: Response,
    selected_details: SSGenerativeRequest = Body(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:

        ss_oracle_service = SSOracleService(session)
        generated_title = await ss_oracle_service.generate_sonic_playlist_details(
            ss_generative_data=selected_details, user_email=email
        )
        payload = CommonResponse(
            success=True,
            message="Sonic Playlist title generated",
            payload=generated_title,
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
    name="Generate sonic supplement cover image based on the track selection",
)
async def generate_ss_cover_image_based_tracks(
    response: Response,
    selected_details: SSGenerativeRequest = Body(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:

        ss_oracle_service = SSOracleService(session)
        generated_title = await ss_oracle_service.generate_cover_image(
            ss_generative_data=selected_details, user_email=email
        )
        payload = CommonResponse(
            success=True,
            message="Sonic playlist cover image generated",
            payload=generated_title,
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
    "/generate-square-cover-image",
    name="Generate sonic supplement square cover image based on the track selection",
)
async def generate_ss_cover_image_based_tracks(
    response: Response,
    selected_details: SSGenerativeRequest = Body(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:

        ss_oracle_service = SSOracleService(session)
        generated_title = await ss_oracle_service.generate_square_image(
            ss_generative_data=selected_details, user_email=email
        )
        payload = CommonResponse(
            success=True,
            message="Sonic playlist cover image generated",
            payload=generated_title,
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
    "/sonic-summary",
    name="Generate sonic supplement spread summary based on the track selection",
)
async def generate_ss_cover_image_based_tracks(
    response: Response,
    selected_details: SSGenerativeRequest = Body(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:

        ss_oracle_service = SSOracleService(session)
        async_summary = ss_oracle_service.generate_sonic_supplement_spread_summary(
            ss_generative_data=selected_details, user_email=email
        )
        return StreamingResponse(async_summary, media_type="text/text")

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
