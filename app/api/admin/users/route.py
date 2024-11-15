from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.admin.users.service import AdminUserService
from app.auth.auth_handler import AuthHandler
from app.common.http_response_model import CommonResponse
from app.database import db_session

router = APIRouter()


@router.get("", name="Get all user details")
async def get_all_user_records(
    response: Response,
    email: str = Depends(AuthHandler()),
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=0),
    search: str = Query(None),
    sort_column: str = Query(None),
    sort_direction: str = Query(None),
    session: AsyncSession = Depends(db_session),
):

    try:
        admin_user_service = AdminUserService(session)
        users = await admin_user_service.get_all_user_details(
            page, per_page, search, sort_column, sort_direction
        )
        payload = CommonResponse(
            message="Successfully fetch user details.",
            success=True,
            payload=users,
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
