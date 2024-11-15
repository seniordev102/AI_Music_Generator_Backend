from typing import List

from fastapi import (
    APIRouter,
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

from app.api.sonic_supplement.service import SonicSupplementService
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.models import SonicSupplements
from app.schemas import CreateSonicSupplement, UpdateSonicSupplement

router = APIRouter()


@router.get("", name="Get all sonic supplement collections")
async def get_all_sonic_supplements(
    response: Response,
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=0),
    session: AsyncSession = Depends(db_session),
):

    try:
        sonic_supplement_service = SonicSupplementService(session)
        sonic_supplement_collections, page_meta = (
            await sonic_supplement_service.get_all_sonic_supplement_collections(
                page, per_page
            )
        )
        payload = CommonResponse[List[SonicSupplements]](
            message="Successfully fetched sonic supplement collections",
            success=True,
            payload=sonic_supplement_collections,
            meta=page_meta,
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
    "/{sonic_supplement_collection_id}", name="Get a sonic supplement collection"
)
async def get_sonic_supplement_collection_by_id(
    response: Response,
    sonic_supplement_collection_id: UUID4 = Path(
        ..., title="The ID of the sonic supplement collection to fetch"
    ),
    session: AsyncSession = Depends(db_session),
):

    try:
        sonic_supplement_collection_service = SonicSupplementService(session)
        collection = await sonic_supplement_collection_service.get_sonic_supplement_collection_by_id(
            sonic_supplement_collection_id
        )

        payload = CommonResponse(
            success=True,
            message="Sonic Supplement Collection fetched successfully",
            payload=collection,
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


@router.post("", name="Create a sonic supplement collection")
async def create_sonic_supplement_collection(
    response: Response,
    cover_image_file: UploadFile = File(
        None, title="The cover image file of the sonic supplement collection"
    ),
    square_cover_image_file: UploadFile = File(
        None, title="The square cover image file of the sonic supplement collection"
    ),
    name: str = Form(..., title="The name of the collection"),
    description: str = Form(
        None, title="The description of the sonic supplement collection"
    ),
    short_description: str = Form(
        None, title="The short description sonic supplement of the collection"
    ),
    benefits: str = Form(None, title="The benefits sonic supplement of the collection"),
    track_ids: str = Form(
        None, title="The track ids sonic supplement of the collection"
    ),
    order_seq: int = Form(
        None, title="The order sequence of the sonic supplement collection"
    ),
    session: AsyncSession = Depends(db_session),
):

    try:

        collection_data = CreateSonicSupplement(
            name=name,
            description=description,
            short_description=short_description,
            benefits=benefits,
            track_ids=track_ids,
            order_seq=order_seq,
        )
        sonic_supplement_collection_service = SonicSupplementService(session)
        created_collection = await sonic_supplement_collection_service.create_sonic_supplement_collection(
            cover_image_file, square_cover_image_file, collection_data
        )
        payload = CommonResponse(
            success=True,
            message="Sonic Supplement Collection created successfully",
            payload=created_collection,
        )
        response.status_code = status.HTTP_201_CREATED
        return payload

    except HTTPException as http_err:
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        payload = CommonResponse(
            success=False,
            message="Error creating Sonic Supplement Collection",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.patch(
    "/{sonic_supplement_collection_id}", name="Update a Sonic Supplement collection"
)
async def update_sonic_supplement_collection(
    response: Response,
    sonic_supplement_collection_id: UUID4 = Path(
        ..., title="The ID of the sonic supplement collection to update"
    ),
    cover_image_file: UploadFile = File(
        None, title="The cover image file of the sonic supplement collection"
    ),
    square_cover_image_file: UploadFile = File(
        None, title="The cover image file of the sonic supplement collection"
    ),
    name: str = Form(None, title="The name of the sonic supplement collection"),
    description: str = Form(
        None, title="The description of the sonic supplement collection"
    ),
    short_description: str = Form(
        None, title="The short description of the sonic supplement collection"
    ),
    benefits: str = Form(None, title="The benefits of the sonic supplement collection"),
    order_seq: int = Form(None, title="The order sequence of the collection"),
    track_ids: str = Form(
        None, title="The track ids of the sonic supplement collection"
    ),
    session: AsyncSession = Depends(db_session),
):

    try:

        sonic_supplement_collection_service = SonicSupplementService(session)
        collection_update_data = UpdateSonicSupplement(
            name=name,
            description=description,
            short_description=short_description,
            order_seq=order_seq,
            benefits=benefits,
            track_ids=track_ids,
        )
        updated_sonic_supplement_collection = await sonic_supplement_collection_service.update_sonic_supplement_collection_collection(
            sonic_supplement_collection_id,
            collection_update_data,
            cover_image_file,
            square_cover_image_file,
        )
        payload = CommonResponse(
            success=True,
            message="Sonic Supplement Collection updated successfully",
            payload=updated_sonic_supplement_collection,
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
        payload = CommonResponse(
            success=False,
            message="Error creating sonic supplement collection",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.delete(
    "/{sonic_supplement_collection_id}", name="Delete sonic supplement collection"
)
async def delete_sonic_supplement_collection(
    response: Response,
    sonic_supplement_collection_id: UUID4 = Path(
        ..., title="The ID of the sonic supplement collection to delete"
    ),
    session: AsyncSession = Depends(db_session),
):

    try:

        sonic_supplement_collection_service = SonicSupplementService(session)
        await sonic_supplement_collection_service.delete_collection(
            sonic_supplement_collection_id
        )
        payload = CommonResponse(
            success=True,
            message="Sonic Supplement Collection deleted successfully",
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
        payload = CommonResponse(
            success=False,
            message="Error creating sonic supplement collection",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


# get tracks belongs to a collection
@router.get(
    "/{sonic_supplement_collection_id}/tracks",
    name="Get all the tracks of a sonic supplement collection",
)
async def get_all_tracks_belongs_to_sonic_supplement_collection(
    response: Response,
    sonic_supplement_collection_id: UUID4 = Path(
        ..., title="The ID of the sonic supplement collection to fetch"
    ),
    session: AsyncSession = Depends(db_session),
):
    try:
        sonic_supplement_collection_service = SonicSupplementService(session)
        sonic_supplement_collection = await sonic_supplement_collection_service.get_sonic_supplement_collection_by_id(
            sonic_supplement_collection_id
        )

        #  get all tracks of an album
        tracks = (
            await sonic_supplement_collection_service.get_all_sonic_supplement_tracks(
                sonic_supplement_collection_id
            )
        )

        payload_data = {
            "sonic_supplement_collection": sonic_supplement_collection,
            "tracks": tracks,
        }

        payload = CommonResponse(
            success=True,
            message="Sonic Collection and tracks details fetched successfully",
            payload=payload_data,
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
        payload = CommonResponse(
            success=False, message="Error creating album", payload=str(e)
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get(
    "/{sonic_supplement_collection_id}/recommended",
    name="Get all the recommended sonic supplement collections",
)
async def get_all_tracks_belongs_to_sonic_supplement_collection(
    response: Response,
    sonic_supplement_collection_id: UUID4 = Path(
        ..., title="The ID of the sonic supplement collection to fetch"
    ),
    session: AsyncSession = Depends(db_session),
):
    try:
        sonic_supplement_collection_service = SonicSupplementService(session)
        sonic_supplement_collections = await sonic_supplement_collection_service.get_all_sonic_supplement_recommended_collections(
            sonic_supplement_collection_id
        )

        payload = CommonResponse(
            success=True,
            message="Recommended Sonic Collections fetched successfully",
            payload=sonic_supplement_collections,
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
        payload = CommonResponse(
            success=False,
            message="Error fetching recommended sonic supplement collections",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get("/search/list", name="Search sonic supplement collections")
async def search_collections(
    response: Response,
    query: str = Query(None, title="Search Query"),
    session: AsyncSession = Depends(db_session),
):
    try:
        sonic_supplement_service = SonicSupplementService(session)
        collections = (
            await sonic_supplement_service.search_sonic_supplement_collections(query)
        )
        payload = CommonResponse(
            message="Successfully fetched search results",
            success=True,
            payload=collections,
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
