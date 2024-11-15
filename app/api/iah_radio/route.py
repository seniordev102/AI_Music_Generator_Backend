from typing import List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    HTTPException,
    Query,
    status,
)
from fastapi.responses import Response
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.iah_radio.service import IAHRadioService
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.models import Collection, Track
from app.schemas import GetIahRadioTracks

router = APIRouter()


class TrackWithCollection(BaseModel):
    track: Track
    collection: Collection


class GetTracksBasedOnIahRadioCollectionResponse(BaseModel):
    tracks: List[TrackWithCollection]
    salt: str


@router.post("", name="Get all the tracks for based on iah radio collections")
async def get_tracks_based_on_iah_radio_collection(
    response: Response,
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=0),
    salt: Optional[str] = Query(None),  # Add optional salt parameter
    request_payload: GetIahRadioTracks = Body(...),
    session: AsyncSession = Depends(db_session),
):
    try:
        iah_radio_service = IAHRadioService(session)
        structured_data, page_meta, salt = (
            await iah_radio_service.get_all_tracks_for_iah_radio_based_on_collections(
                page=page, page_size=per_page, filter_data=request_payload, salt=salt
            )
        )

        # Convert dictionaries to TrackWithCollection objects
        tracks_with_collections = [
            TrackWithCollection(
                track=Track(**item["track"]),
                collection=Collection(**item["collection"]),
            )
            for item in structured_data
        ]

        result = {
            "tracks": tracks_with_collections,
            "salt": salt,
        }
        # Include salt in the response metadata
        meta = {**page_meta.dict(), "salt": salt}
        payload = CommonResponse[GetTracksBasedOnIahRadioCollectionResponse](
            message="Successfully fetched all tracks for iah radio",
            success=True,
            payload=result,
            meta=meta,
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


# @router.post("", name="Get all the tracks for based on iah radio collections")
# async def get_tracks_based_on_iah_radio_collection(
#     response: Response,
#     page: int = Query(1, ge=1),
#     per_page: int = Query(100, ge=0),
#     request_payload: GetIahRadioTracks = Body(...),
#     session: AsyncSession = Depends(db_session),
# ):

#     try:
#         iah_radio_service = IAHRadioService(session)
#         structured_data, page_meta = (
#             await iah_radio_service.get_all_tracks_for_iah_radio_based_on_collections(
#                 page=page, page_size=per_page, filter_data=request_payload
#             )
#         )

#         # Convert dictionaries to TrackWithCollection objects
#         tracks_with_collections = [
#             TrackWithCollection(
#                 track=Track(**item["track"]),
#                 collection=Collection(**item["collection"]),
#             )
#             for item in structured_data
#         ]

#         payload = CommonResponse[List[TrackWithCollection]](
#             message="Successfully fetched all tracks for iah radio",
#             success=True,
#             payload=tracks_with_collections,
#             meta=page_meta,
#         )
#         response.status_code = status.HTTP_200_OK
#         return payload

#     except HTTPException as http_err:
#         payload = CommonResponse(
#             success=False, message=str(http_err.detail), payload=None
#         )
#         response.status_code = http_err.status_code
#         return payload

#     except Exception as e:
#         payload = CommonResponse(success=False, message=str(e), payload=None)
#         response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
#         return payload


# TODO: protect only admin can access this endpoint
@router.get(
    "/generate-lyrics", name="Automatically generate lyrics for iah radio tracks"
)
async def get_tracks(
    response: Response,
    session: AsyncSession = Depends(db_session),
):

    try:
        iah_radio_service = IAHRadioService(session)
        result = await iah_radio_service.generate_lyrics_for_iah_radio_tracks()

        payload = CommonResponse(
            message="Successfully generated lyrics for all iah radio lyrical tracks",
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


@router.get(
    "/generate-lyrics/sync",
    name="Automatically generate lyrics on tracks for iah radio tracks",
)
async def sync_missing_lyrics_for_tracks(
    background_tasks: BackgroundTasks,
    response: Response,
    session: AsyncSession = Depends(db_session),
):

    try:
        iah_radio_service = IAHRadioService(session)
        background_tasks.add_task(iah_radio_service.generate_missing_lyrics)

        payload = CommonResponse(
            message="Successfully generated lyrics for all iah radio lyrical tracks",
            success=True,
            payload=None,
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


@router.get("/collections", name="Get iah radio collections")
async def get_iah_radio_collections(
    response: Response,
    session: AsyncSession = Depends(db_session),
):

    try:
        iah_radio_service = IAHRadioService(session)
        collections_list = await iah_radio_service.get_iah_radio_collections()

        payload = CommonResponse(
            message="IAH radio collections fetched",
            success=True,
            payload=collections_list,
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
