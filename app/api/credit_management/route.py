from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.auth.service import AuthService
from app.api.credit_management.monthly_allocation.route import (
    router as monthly_allocation_router,
)
from app.api.credit_management.service import CreditManagementService
from app.api.credit_management.stripe.route import router as cm_stripe_router
from app.api.credit_management.stripe.service import StripeCreditManagementService
from app.auth.auth_handler import AuthHandler
from app.common.http_response_model import CommonResponse
from app.config import settings
from app.database import db_session
from app.models import TransactionSource, TransactionType
from app.schemas import (
    AddCreditsRequest,
    AdminAddCreditsRequest,
    DeductCreditsRequest,
    ValidateCreditTransferRequest,
)

router = APIRouter()


@router.get("/balance", name="Get user credit balance")
async def get_user_balance(
    response: Response,
    at_timestamp: Optional[datetime] = None,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
) -> CommonResponse:
    try:
        service = CreditManagementService(session)
        result = await service.get_user_credit_details(
            email=email, at_timestamp=at_timestamp
        )

        payload = CommonResponse(
            message="User credit balance details fetched successfully",
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


@router.get("/transactions", name="Get transaction history")
async def get_transaction_history(
    response: Response,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    transaction_type: Optional[TransactionType] = None,
    source: Optional[TransactionSource] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
) -> CommonResponse:
    try:
        service = CreditManagementService(session)
        transactions, pagination = await service.get_transaction_history(
            user_email=email,
            page=page,
            page_size=page_size,
            tx_type=transaction_type,
            source=source,
            start_date=start_date,
            end_date=end_date,
        )

        payload = CommonResponse(
            message="Transaction history fetched successfully",
            success=True,
            payload=transactions,
            meta=pagination,
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


@router.get("/analytics", name="Get transaction analytics")
async def get_transaction_analytics(
    response: Response,
    days: int = Query(30, ge=1, le=365),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
) -> CommonResponse:
    """Get transaction analytics for a specified time period"""
    try:
        service = CreditManagementService(session)
        result = await service.get_transaction_analytics(
            user_email=email, time_range=timedelta(days=days)
        )

        payload = CommonResponse(
            message="Transaction analytics fetched successfully",
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


@router.post("/deduct-credits", name="Deduct credits")
async def deduct_credits(
    response: Response,
    request: DeductCreditsRequest,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
) -> CommonResponse:
    """Deduct credits from user balance"""
    try:
        service = CreditManagementService(session)
        result = await service.deduct_credits(
            user_email=email,
            amount=request.amount,
            api_endpoint=request.api_endpoint,
            description=request.description,
            metadata=request.metadata,
        )

        payload = CommonResponse(
            message="Credits deducted successfully", success=True, payload=result
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


@router.get("/subscription-details", name="Get subscription details")
async def get_subscription_details(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
) -> CommonResponse:
    """Get user's current subscription details"""
    try:
        service = CreditManagementService(session)
        result = await service.get_subscription_details(email)

        payload = CommonResponse(
            message="Subscription details fetched successfully",
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


@router.post("/admin/add-credits", name="Admin add credits")
async def admin_add_credits(
    response: Response,
    request: AdminAddCreditsRequest,
    admin_email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
) -> CommonResponse:
    """Admin endpoint to add credits to any user (Admin only)"""
    try:
        # Check admin status
        auth_service = AuthService(session)
        await auth_service.is_admin_check(admin_email)

        cm_service = CreditManagementService(session)
        result = await cm_service.add_credits(
            user_email=request.user_email,
            package_id=request.package_id,
            source=TransactionSource.SYSTEM,
            description=request.description,
            metadata={"added_by_admin": admin_email, **(request.metadata or {})},
        )

        payload = CommonResponse(
            message=f"Credits added to {request.user_email} successfully",
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


@router.post("/validate-transfer", name="Validate p2p credit transfer")
async def validate_credit_transfer(
    response: Response,
    request: ValidateCreditTransferRequest,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
) -> CommonResponse:
    try:

        cm_service = CreditManagementService(session)
        result = await cm_service.validate_transfer_request(
            user_email=email,
            receiver_email=request.receiver_email,
            amount=request.amount,
        )

        payload = CommonResponse(
            message=f"Credit transfer request has been validated",
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


@router.post("/transfer", name="Execute p2p credit transfer")
async def validate_credit_transfer(
    response: Response,
    request: ValidateCreditTransferRequest,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:

        cm_service = CreditManagementService(session)
        result = await cm_service.transfer_credits(
            from_email=email, to_email=request.receiver_email, amount=request.amount
        )

        payload = CommonResponse(
            message=f"P2p credit transfer has been complete",
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


@router.post(
    "/yearly-subscription/monthly-credits",
    name="Process monthly credits for yearly subscriptions",
)
async def process_monthly_credits_for_yearly_subscriptions(
    response: Response,
    user_email: Optional[str] = None,
    api_key: str = Header(...),
    session: AsyncSession = Depends(db_session),
) -> CommonResponse:
    """
    Process monthly credit allocation for yearly subscriptions.
    This endpoint should be called by a cronjob once a month.

    Credits are added as SUBSCRIPTION_RENEWAL transactions with a monthly_allocation flag.

    If user_email is provided, process only for that user, otherwise process for all users with yearly subscriptions.

    Requires an API key for security.
    """
    try:
        # Validate API key
        if api_key != settings.CRON_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
            )

        # Initialize service
        credit_management_service = CreditManagementService(session)
        stripe_service = StripeCreditManagementService(session)

        # Process monthly credits
        result = await stripe_service.process_yearly_subscription_monthly_credits(
            user_email
        )

        payload = CommonResponse(
            success=True,
            message="Successfully processed monthly credits for yearly subscriptions",
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


router.include_router(cm_stripe_router, prefix="/stripe")
router.include_router(monthly_allocation_router)
