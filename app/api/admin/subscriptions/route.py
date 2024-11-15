import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.admin.subscriptions.service import AdminSubscriptionService
from app.api.deps import get_current_user
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.models import User

router = APIRouter()


@router.get("", name="Get all user subscriptions")
async def get_all_user_subscriptions(
    response: Response,
    session: AsyncSession = Depends(db_session),
):
    try:
        admin_subscription_service = AdminSubscriptionService(session)
        result = await admin_subscription_service.get_user_subscriptions()

        # Get the absolute path to the CSV file
        csv_path = os.path.abspath("user_subscriptions.csv")

        payload = CommonResponse(
            message="Successfully fetched user subscription details and generated CSV file.",
            success=True,
            payload={"subscriptions": result, "csv_file_path": csv_path},
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


@router.get("/download-csv", name="Download user subscriptions CSV")
async def download_user_subscriptions_csv(
    session: AsyncSession = Depends(db_session),
):
    try:
        # First generate the CSV file
        admin_subscription_service = AdminSubscriptionService(session)
        await admin_subscription_service.get_user_subscriptions()

        # Return the file as a download
        csv_path = os.path.abspath("user_subscriptions.csv")

        if not os.path.exists(csv_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="CSV file not found"
            )

        return FileResponse(
            path=csv_path, filename="user_subscriptions.csv", media_type="text/csv"
        )

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}",
        )


@router.get("/customer/{customer_id}", name="Get subscription details by customer ID")
async def get_subscription_details_by_customer_id(
    customer_id: str,
    response: Response,
    session: AsyncSession = Depends(db_session),
):
    try:
        admin_subscription_service = AdminSubscriptionService(session)
        result = (
            await admin_subscription_service.get_subscription_details_by_customer_id(
                customer_id
            )
        )

        payload = CommonResponse(
            message="Successfully fetched subscription details.",
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


@router.get("/user/{email}", name="Get subscription details by user email")
async def get_subscription_details_by_email(
    email: str,
    response: Response,
    session: AsyncSession = Depends(db_session),
):
    try:
        admin_subscription_service = AdminSubscriptionService(session)
        result = await admin_subscription_service.get_subscription_details_by_email(
            email
        )

        payload = CommonResponse(
            message="Successfully fetched subscription details.",
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


@router.post("/migrate", name="Migrate subscriptions to credit-based system")
async def migrate_subscriptions(
    email: Optional[str] = None,
    execute: bool = False,
    response: Response = None,
    session: AsyncSession = Depends(db_session),
    current_user: User = Depends(get_current_user),
):
    try:
        # Ensure the user is an admin
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admin users can perform this action",
            )

        admin_subscription_service = AdminSubscriptionService(session)
        result = await admin_subscription_service.migrate_subscriptions_to_credit_based(
            email=email, execute=execute
        )

        payload = CommonResponse(
            message=result["message"],
            success=result["success"],
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
