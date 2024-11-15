from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.affiliate.service import UserAffiliateService
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.schemas import CreateAffiliateUser

router = APIRouter()


@router.post("/create-user", name="Get all subscriptions plans")
async def create_user_by_affiliate(
    response: Response,
    payload: CreateAffiliateUser,
    session: AsyncSession = Depends(db_session),
) -> CommonResponse:

    try:
        affiliate_service = UserAffiliateService(session)
        subscriptions = await affiliate_service.create_affiliate_user(
            affiliate_data=payload
        )
        payload = CommonResponse(
            message="Successfully created affiliate user and email has been sent",
            success=True,
            payload=subscriptions,
        )
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
