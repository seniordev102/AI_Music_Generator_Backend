from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.admin.ac.service import ActiveCampaignService
from app.auth.auth_handler import AuthHandler
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.schemas import GetActiveCampaignContact

router = APIRouter()


@router.get("/contact/sync", name="Sync all contacts to active campaign portal")
async def sync_contact_to_active_campaign(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        ac_service = ActiveCampaignService(session)
        sync_status = await ac_service.sync_all_contact_to_active_campaign()
        payload = CommonResponse(
            message="Active campaign sync completed.",
            success=True,
            payload=sync_status,
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


@router.get("/contact/ac/list", name="Get all active campaign contacts")
async def get_all_active_campaign_contact_list(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        ac_service = ActiveCampaignService(session)
        all_contacts = await ac_service.get_all_active_campaign_contact_list()
        payload = CommonResponse(
            message="All active campaign contacts fetched successfully",
            success=True,
            payload=all_contacts,
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


@router.post("/contact/ac/get", name="Get active campaign contact by email")
async def get_ac_contact_by_email(
    response: Response,
    ac_data: GetActiveCampaignContact,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        ac_service = ActiveCampaignService(session)
        all_contacts = await ac_service.get_new_ac_contact_by_email(email=ac_data.email)
        payload = CommonResponse(
            message="Active campaign contact fetched successfully",
            success=True,
            payload=all_contacts,
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
