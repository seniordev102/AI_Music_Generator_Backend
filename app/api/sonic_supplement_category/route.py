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

from app.api.sonic_supplement_category.service import SonicSupplementCategoryService
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.models import SonicSupplementCategory
from app.schemas import CreateSonicSupplementCategory, UpdateSonicSupplementCategory

router = APIRouter()


@router.get("", name="Get all sonic supplement categories")
async def get_all_sonic_supplement_categories(
    response: Response,
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=0),
    session: AsyncSession = Depends(db_session),
):

    try:
        sonic_supplement_category_service = SonicSupplementCategoryService(session)
        categories, page_meta = (
            await sonic_supplement_category_service.get_all_sonic_supplement_categories(
                page, per_page
            )
        )
        payload = CommonResponse[List[SonicSupplementCategory]](
            message="Successfully fetched sonic supplement categories",
            success=True,
            payload=categories,
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
    "/{sonic_supplement_category_id}", name="Get a sonic supplement category by ID"
)
async def get_sonic_supplement_category_by_id(
    response: Response,
    sonic_supplement_category_id: UUID4 = Path(
        ..., title="The ID of the sonic supplement category to fetch"
    ),
    session: AsyncSession = Depends(db_session),
):

    try:
        sonic_supplement_category_service = SonicSupplementCategoryService(session)
        category = (
            await sonic_supplement_category_service.get_sonic_supplement_category_by_id(
                sonic_supplement_category_id
            )
        )

        payload = CommonResponse(
            success=True,
            message="Sonic Supplement Category fetched successfully",
            payload=category,
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


@router.post("", name="Create a sonic supplement category")
async def create_category(
    response: Response,
    cover_image_file: UploadFile = File(
        None, title="The cover image file of the category"
    ),
    name: str = Form(..., title="The name of the category"),
    collection_ids: str = Form(None, title="Collection ids of the collection"),
    description: str = Form(None, title="The description of the category"),
    order_seq: int = Form(None, title="The order sequence of the category"),
    session: AsyncSession = Depends(db_session),
):

    try:

        category_data = CreateSonicSupplementCategory(
            name=name,
            description=description,
            collection_ids=collection_ids,
            order_seq=order_seq,
        )
        sonic_supplement_category_service = SonicSupplementCategoryService(session)
        category_record = (
            await sonic_supplement_category_service.create_sonic_supplement_category(
                cover_image_file, category_data
            )
        )
        payload = CommonResponse(
            success=True,
            message="sonic supplement category created successfully",
            payload=category_record,
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
            message="Error creating sonic supplement category",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.patch(
    "/{sonic_supplement_category_id}", name="Update a sonic supplement category"
)
async def update_category(
    response: Response,
    sonic_supplement_category_id: UUID4 = Path(
        ..., title="The ID of the sonic supplement category to update"
    ),
    cover_image_file: UploadFile = File(
        None, title="The cover image file of the collection"
    ),
    name: str = Form(None, title="The name of the collection"),
    description: str = Form(None, title="The description of the collection"),
    order_seq: int = Form(None, title="The order sequence of the collection"),
    collection_ids: str = Form(None, title="The ID list of the collections"),
    session: AsyncSession = Depends(db_session),
):

    try:

        sonic_supplement_category_service = SonicSupplementCategoryService(session)
        category_data = UpdateSonicSupplementCategory(
            name=name,
            description=description,
            order_seq=order_seq,
            collection_ids=collection_ids,
        )
        updated_category = (
            await sonic_supplement_category_service.update_sonic_supplement_category(
                sonic_supplement_category_id, cover_image_file, category_data
            )
        )
        payload = CommonResponse(
            success=True,
            message="Sonic Supplement Category updated successfully",
            payload=updated_category,
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
            message="Error updating sonic supplement category",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.delete(
    "/{sonic_supplement_category_id}", name="Delete the sonic supplement category"
)
async def delete_sonic_supplement_category(
    response: Response,
    sonic_supplement_category_id: UUID4 = Path(
        ..., title="The ID of the sonic supplement category to delete"
    ),
    session: AsyncSession = Depends(db_session),
):

    try:

        sonic_supplement_category_service = SonicSupplementCategoryService(session)
        await sonic_supplement_category_service.delete_sonic_supplement_category(
            sonic_supplement_category_id
        )
        payload = CommonResponse(
            success=True,
            message="Sonic Supplement Category deleted successfully",
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
            message="Error while deleting the sonic supplement category",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


# get all collections belongs to a sonic supplement category
@router.get(
    "/{sonic_supplement_category_id}/collections",
    name="Get all the collections belongs to a sonic supplement category",
)
async def get_all_collections_belongs_to_sonic_supplement_category(
    response: Response,
    sonic_supplement_category_id: UUID4 = Path(
        ..., title="The ID of the sonic supplement category to fetch"
    ),
    session: AsyncSession = Depends(db_session),
):
    try:
        sonic_supplement_category_service = SonicSupplementCategoryService(session)
        collections = await sonic_supplement_category_service.get_collections_by_sonic_supplement_category(
            sonic_supplement_category_id
        )

        payload = CommonResponse(
            success=True,
            message="Sonic Supplement Collections fetched successfully",
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
        payload = CommonResponse(
            success=False,
            message="Error while fetching collections belongs to a sonic supplement category",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get(
    "/{sonic_supplement_category_id}/randomized/tracks/{track_count}",
    name="Generate random track list based on sonic supplement category id",
)
async def generate_random_track_list(
    response: Response,
    sonic_supplement_category_id: UUID4 = Path(
        ..., title="The ID of the sonic supplement category to fetch"
    ),
    track_count: int = Path(..., title="Numbers of track count to generate"),
    session: AsyncSession = Depends(db_session),
):

    try:
        sonic_Supplement_category_service = SonicSupplementCategoryService(session)
        tracks = await sonic_Supplement_category_service.get_random_tracks_based_on_sonic_Supplement_category(
            sonic_supplement_category_id, track_count
        )
        payload = CommonResponse(
            message="Successfully generate random track list",
            success=True,
            payload=tracks,
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
