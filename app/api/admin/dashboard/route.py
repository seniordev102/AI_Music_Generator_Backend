from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.admin.dashboard.service import DashboardStatService
from app.auth.auth_handler import AuthHandler
from app.common.http_response_model import CommonResponse
from app.database import db_session

router = APIRouter()


@router.get("/statistic", name="Get all site statistics")
async def get_all_site_statistics(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        dashboard_service = DashboardStatService(session)
        stats = await dashboard_service.get_all_dashboard_stats()
        payload = CommonResponse(
            message="Successfully fetch dashboard statistics.",
            success=True,
            payload=stats,
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
