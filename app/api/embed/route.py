import random
import uuid
from typing import List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import Response
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.embed.service import EmbedService
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.models import Track
from app.schemas import CreateTrack, GetTrackIds, UpdateTrack

router = APIRouter()


@router.get("/sonic-playlist/search", name="Search all craft my sonic playlist")
async def search_cms_playlist(
    response: Response,
    query: str = Query(None, title="Search Query"),
    session: AsyncSession = Depends(db_session),
):

    try:
        embed_service = EmbedService(session)
        playlists = await embed_service.search_all_craft_my_sonic(query=query)
        payload = CommonResponse[List[dict]](
            message="Successfully fetched all craft my sonic playlists",
            success=True,
            payload=playlists,
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
