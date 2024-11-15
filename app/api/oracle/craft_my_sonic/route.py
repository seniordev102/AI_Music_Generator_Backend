from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.oracle.craft_my_sonic.service import CraftMySonicOracleService
from app.auth.auth_handler import AuthHandler
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.schemas import GenerateCraftMySonicDetails, GenerateCraftMySonicImage

router = APIRouter()


@router.post(
    "/generate-details",
    name="Generate the title and description for the craft my sonic",
)
async def generate_craft_my_sonic_details(
    response: Response,
    cms_details: GenerateCraftMySonicDetails = Body(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:

        cms_Service = CraftMySonicOracleService(session)
        generated_details = await cms_Service.generate_cms_details(
            csm_details=cms_details, user_email=email
        )
        payload = CommonResponse(
            success=True,
            message="Craft My Sonic details generated successfully.",
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
    name="Generate the images for the craft my sonic playlist",
)
async def generate_craft_my_sonic_image(
    response: Response,
    user_request: GenerateCraftMySonicImage = Body(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:

        cms_Service = CraftMySonicOracleService(session)
        generated_image_details = await cms_Service.generate_cms_images(
            user_prompt=user_request.user_prompt, user_email=email
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


@router.post(
    "/generate-cover-image",
    name="Generate the cover image for the craft my sonic playlist",
)
async def generate_craft_my_sonic_image(
    response: Response,
    user_request: GenerateCraftMySonicImage = Body(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:

        cms_Service = CraftMySonicOracleService(session)
        generated_image_details = await cms_Service.generate_cms_cover_image(
            user_prompt=user_request.user_prompt, user_email=email
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


@router.post(
    "/generate-square-image",
    name="Generate the square image for the craft my sonic playlist",
)
async def generate_craft_my_sonic_image(
    response: Response,
    user_request: GenerateCraftMySonicImage = Body(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:

        cms_Service = CraftMySonicOracleService(session)
        generated_image_details = await cms_Service.generate_cms_square_image(
            user_prompt=user_request.user_prompt, user_email=email
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
