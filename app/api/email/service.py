from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.email_utils import send_email
from app.database import db_session
from app.schemas import SendEmail


class EmailService:
    def __init__(self, session: AsyncSession = Depends(db_session)) -> None:
        self.session = session

    async def send_email(self, contact_us_data: SendEmail) -> bool:
        success = await send_email(
            contact_us_data.email,
            contact_us_data.subject,
            contact_us_data.name,
            contact_us_data.message,
        )
        if success:
            return True
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Email could not be sent",
            )
