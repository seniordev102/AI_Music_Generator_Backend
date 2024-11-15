from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from fastapi.responses import Response
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.subscription_config.service import SubscriptionConfigService
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.schemas import CreateSubscriptionConfig, UpdateSubscriptionConfig

router = APIRouter()


@router.get("", name="Get all subscription configs")
async def get_all_subscription_configs(
    response: Response, session: AsyncSession = Depends(db_session)
):

    try:
        sub_config_service = SubscriptionConfigService(session)
        new_subscription_config = await sub_config_service.get_all_plans()
        return new_subscription_config

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


@router.get("/seed", name="Seed all subscription configs")
async def seed_all_initial_subscription_configs(
    response: Response, session: AsyncSession = Depends(db_session)
):

    try:
        sub_config_service = SubscriptionConfigService(session)
        new_subscription_config = (
            await sub_config_service.seed_all_subscription_configs()
        )
        return new_subscription_config

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


@router.post("/create", name="Create a subscription config")
async def create_subscription_config(
    response: Response,
    subscription_config: CreateSubscriptionConfig,
    session: AsyncSession = Depends(db_session),
):

    try:
        sub_config_service = SubscriptionConfigService(session)
        new_subscription_config = await sub_config_service.create_subscription_config(
            subscription_config
        )
        return new_subscription_config

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


@router.patch("/update/{subscription_config_id}", name="Edit subscription config")
async def edit_subscription_config(
    response: Response,
    subscription_config_id: UUID4,
    subscription_config: UpdateSubscriptionConfig,
    session: AsyncSession = Depends(db_session),
):

    try:
        sub_config_service = SubscriptionConfigService(session)
        new_subscription_config = await sub_config_service.update_subscription_config(
            subscription_config_id, subscription_config
        )
        return new_subscription_config

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
