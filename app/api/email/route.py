from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from fastapi.responses import Response
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.email.service import EmailService
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.schemas import SendEmail

router = APIRouter()


@router.post("", name="Send an email")
async def send_email(
    response: Response,
    contact_us_data: SendEmail,
    session: AsyncSession = Depends(db_session),
):

    try:
        email_service = EmailService(session)
        result = await email_service.send_email(contact_us_data)
        payload = CommonResponse(
            success=True, message="Email sent successfully", payload=result
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        print(f"HTTP error occurred: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        print(f"An error occurred: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload
