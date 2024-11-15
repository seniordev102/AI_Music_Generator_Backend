from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.oracle.user_prompt.service import UserCustomPromptService
from app.auth.auth_handler import AuthHandler
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.schemas import CreateOrUpdateUserPrompt

router = APIRouter()


@router.get("/iah", name="Get user custom IAH prompt")
async def get_user_iah_custom_prompt(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        user_custom_prompt_service = UserCustomPromptService(session)
        result = await user_custom_prompt_service.get_user_iah_custom_prompt(
            user_email=email,
        )
        payload = CommonResponse(
            message="User IAH custom prompt has been fetch",
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
        payload = CommonResponse(
            success=False,
            message="Error while fetching user IAH custom prompt",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.post("/iah", name="Create or update IAH user custom prompt")
async def create_or_update_iah_custom_prompt(
    response: Response,
    payload: CreateOrUpdateUserPrompt,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        user_custom_prompt_service = UserCustomPromptService(session)
        result = (
            await user_custom_prompt_service.create_or_update_iah_user_custom_prompt(
                user_email=email,
                custom_prompt=payload.user_prompt,
                is_active=payload.is_active,
            )
        )
        payload = CommonResponse(
            message="User IAH custom prompt has been updated",
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
        payload = CommonResponse(
            success=False,
            message="Error while updating user IAH custom prompt",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get("/sra", name="Get user custom SRA prompt")
async def get_user_sra_custom_prompt(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        user_custom_prompt_service = UserCustomPromptService(session)
        result = await user_custom_prompt_service.get_user_sra_custom_prompt(
            user_email=email,
        )
        payload = CommonResponse(
            message="User SRA custom prompt has been fetch",
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
        payload = CommonResponse(
            success=False,
            message="Error while fetching user IAH custom prompt",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.post("/sra", name="Create or update SRA user custom prompt")
async def create_or_update_sra_custom_prompt(
    response: Response,
    payload: CreateOrUpdateUserPrompt,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        user_custom_prompt_service = UserCustomPromptService(session)
        result = (
            await user_custom_prompt_service.create_or_update_sra_user_custom_prompt(
                user_email=email,
                custom_prompt=payload.user_prompt,
                is_active=payload.is_active,
            )
        )
        payload = CommonResponse(
            message="User SRA custom prompt has been updated",
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
        payload = CommonResponse(
            success=False,
            message="Error while updating user SRA custom prompt",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload
