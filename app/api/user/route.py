from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from fastapi.responses import Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.user.service import UserService
from app.auth.auth_handler import AuthHandler
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.schemas import ChangePasswordRequest, UpdateAPIUsage, UpdateUser
from app.stripe.stripe_service import StripeService

router = APIRouter()


# register a new user
@router.patch("/update", name="Update user details")
async def register_user(
    response: Response,
    update_user: UpdateUser = Body(...),
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
) -> CommonResponse:
    try:

        user_service = UserService(session)
        user = await user_service.update_user(email, update_user)

        payload = CommonResponse(
            message="User has been updated successfully",
            success=True,
            payload=user,
            meta=None,
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


@router.delete("/delete", name="Delete user details")
async def register_user(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
) -> CommonResponse:
    try:

        user_service = UserService(session)
        user = await user_service.delete_user(email)

        payload = CommonResponse(
            message="User has been deleted successfully",
            success=True,
            payload=user,
            meta=None,
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


@router.patch("/change-password", name="Change current logged in user password")
async def change_current_user_password(
    response: Response,
    email: str = Depends(AuthHandler()),
    change_password: ChangePasswordRequest = Body(...),
    session: AsyncSession = Depends(db_session),
) -> CommonResponse:
    try:
        user_service = UserService(session)
        is_changed = await user_service.change_password(
            email, change_password.current_password, change_password.new_password
        )

        payload = CommonResponse(
            message="User password has changed successfully",
            success=True,
            payload=is_changed,
            meta=None,
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


@router.post("/config/update-usage", name="Update user API consumption")
async def update_user_api_consumption(
    response: Response,
    update_api_usage: UpdateAPIUsage,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
) -> CommonResponse:
    try:

        user_service = UserService(session)
        update_response = await user_service.update_user_api_consumption(
            email, update_api_usage
        )

        payload = CommonResponse(
            message="User API consumption has been updated successfully",
            success=True,
            payload=update_response,
            meta=None,
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


@router.get("/search", name="Search users by name or email")
async def search_users_by_name_or_email(
    response: Response,
    query: str = Query(""),
    session: AsyncSession = Depends(db_session),
) -> CommonResponse:
    try:

        user_service = UserService(session)
        user_list = await user_service.search_users_by_name_or_email(query=query)

        payload = CommonResponse(
            message="User list fetched",
            success=True,
            payload=user_list,
            meta=None,
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


@router.get("/{user_id}", name="Search users by name or email")
async def get_user_from_user_id(
    response: Response,
    user_id: str = Path(...),
    session: AsyncSession = Depends(db_session),
) -> CommonResponse:
    try:

        user_service = UserService(session)
        user = await user_service.get_user_from_user_id(user_id=user_id)

        payload = CommonResponse(
            message="User has been fetched",
            success=True,
            payload=user,
            meta=None,
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
