from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import Response, StreamingResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.oracle.summarize.service import OracleSummarizeService
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.schemas import CraftMySonicTrackSummary, SelectedTrackList

router = APIRouter()


@router.post(
    "/track-details",
    name="Create summarized version of selected tracks",
)
async def generate_ss_cover_image_based_tracks(
    response: Response,
    track_details: SelectedTrackList = Body(...),
    session: AsyncSession = Depends(db_session),
):
    try:

        summarize_service = OracleSummarizeService(session)
        async_summary = summarize_service.generate_summary(track_details)
        return StreamingResponse(async_summary, media_type="text/text")

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
    "/cms",
    name="Summarize craft my sonic track details",
)
async def generate_ss_cover_image_based_tracks(
    response: Response,
    cms_summary_details: CraftMySonicTrackSummary = Body(...),
    session: AsyncSession = Depends(db_session),
):
    try:

        summarize_service = OracleSummarizeService(session)
        async_summary = summarize_service.generate_cms_summary(cms_summary_details)
        return StreamingResponse(async_summary, media_type="text/text")

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
