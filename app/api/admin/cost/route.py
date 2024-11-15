from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.admin.cost.service import CostPerActionService
from app.api.auth.service import AuthService
from app.auth.auth_handler import AuthHandler
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.logger.logger import logger
from app.schemas import CreateCostPerAction, UpdateCostPerAction

router = APIRouter()


@router.post("/create", name="Create cost per action")
async def create_cost_per_action(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
    cost_per_action: CreateCostPerAction = Body(...),
):

    try:
        auth_service = AuthService(session)
        await auth_service.is_admin_check(email)

        cost_per_action_service = CostPerActionService(session)
        stats = await cost_per_action_service.create_cost_per_action(
            cost_per_action.action_type, cost_per_action.cost, cost_per_action.endpoint
        )
        payload = CommonResponse(
            message="Successfully created cost per action.",
            success=True,
            payload=stats,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"Error creating cost per action: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"Error creating cost per action: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get("/get-all", name="Get all cost per action")
async def get_all_cost_per_action(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:

        cost_per_action_service = CostPerActionService(session)
        stats = await cost_per_action_service.get_all_cost_per_action()
        payload = CommonResponse(
            message="Successfully fetched all cost per action.",
            success=True,
            payload=stats,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"Error getting all cost per action: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"Error getting all cost per action: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.put("/update", name="Update cost per action")
async def update_cost_per_action(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
    cost_per_action: UpdateCostPerAction = Body(...),
):
    try:
        auth_service = AuthService(session)
        await auth_service.is_admin_check(email)

        cost_per_action_service = CostPerActionService(session)
        stats = await cost_per_action_service.update_cost_per_action(
            cost_per_action.action_type, cost_per_action.cost
        )
        payload = CommonResponse(
            message="Successfully updated cost per action.",
            success=True,
            payload=stats,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"Error updating cost per action: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"Error updating cost per action: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.post("/seed", name="Seed cost per action")
async def seed_cost_per_action(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:
        auth_service = AuthService(session)
        await auth_service.is_admin_check(email)

        cost_per_action_service = CostPerActionService(session)
        await cost_per_action_service.seed_cost_per_action()
        payload = CommonResponse(
            message="Successfully seeded cost per action.",
            success=True,
            payload=None,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"Error seeding cost per action: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"Error seeding cost per action: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload
