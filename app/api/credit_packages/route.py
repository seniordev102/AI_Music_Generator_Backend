from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.auth.service import AuthService
from app.api.credit_packages.service import CreditPackageService
from app.auth.auth_handler import AuthHandler
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.models import SubscriptionPlatform
from app.schemas import UpdatePackageRequest

router = APIRouter()


@router.get("/seed", name="Seed credit packages")
async def seed_credit_packages(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    """
    Seed initial credit packages (Admin only)
    """
    try:
        # perform admin check
        auth_service = AuthService(session)
        await auth_service.is_admin_check(email)

        # seed the database
        credit_package_service = CreditPackageService(session)
        result = await credit_package_service.seed_credit_packages()
        payload = CommonResponse(
            message="Credit packages seeded successfully.",
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
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get("/list", name="List all credit packages")
async def get_all_credit_packages(
    response: Response,
    email: str = Depends(AuthHandler()),
    is_subscription: Optional[bool] = Query(None),
    platform: Optional[SubscriptionPlatform] = Query(None),
    session: AsyncSession = Depends(db_session),
):
    """
    List all credit packages with optional filters
    """
    try:
        credit_package_service = CreditPackageService(session)
        all_packages = await credit_package_service.list_packages(
            is_subscription=is_subscription,
            platform=platform.value if platform else None,
        )
        payload = CommonResponse(
            message="Credit packages fetched successfully",
            success=True,
            payload=all_packages,
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


@router.get("/get/{package_id}", name="Get credit package by id")
async def get_credit_package_by_id(
    response: Response,
    package_id: str,
    platform: Optional[SubscriptionPlatform] = Query(None),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    """
    Get credit package by ID with optional platform-specific pricing
    """
    try:
        credit_package_service = CreditPackageService(session)
        package = await credit_package_service.get_package_by_id(
            package_id, platform=platform.value if platform else None
        )
        payload = CommonResponse(
            message="Credit package fetched successfully",
            success=True,
            payload=package,
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


@router.get("/platform/{platform}/{product_id}", name="Get package by platform ID")
async def get_package_by_platform_id(
    response: Response,
    platform: SubscriptionPlatform,
    product_id: str,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    """
    Get credit package by platform-specific product ID
    """
    try:
        credit_package_service = CreditPackageService(session)
        package = await credit_package_service.get_package_by_platform_id(
            platform=platform.value, product_id=product_id
        )
        payload = CommonResponse(
            message="Credit package fetched successfully",
            success=True,
            payload=package,
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


@router.put("/update/{package_id}", name="Update credit package")
async def update_credit_package(
    response: Response,
    package_id: str,
    update_data: UpdatePackageRequest,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    """
    Update credit package details (Admin only)
    """
    try:
        # perform admin check
        auth_service = AuthService(session)
        await auth_service.is_admin_check(email)

        credit_package_service = CreditPackageService(session)
        updated_package = await credit_package_service.update_package(
            package_id=package_id, update_data=update_data.dict(exclude_unset=True)
        )

        payload = CommonResponse(
            message="Credit package updated successfully",
            success=True,
            payload=updated_package,
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
