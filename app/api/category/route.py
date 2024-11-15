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

from app.api.category.service import CategoryService
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.models import Category
from app.schemas import CreateCategory, UpdateCategory

router = APIRouter()


@router.get("", name="Get all categories")
async def get_all_categories(
    response: Response,
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=0),
    session: AsyncSession = Depends(db_session),
):

    try:
        category_service = CategoryService(session)
        categories, page_meta = await category_service.get_all_categories(
            page, per_page
        )
        payload = CommonResponse[List[Category]](
            message="Successfully fetched categories",
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


@router.get("/all-collections", name="Get all the collections belongs all categories")
async def get_all_collections_belongs_to_category(
    response: Response,
    session: AsyncSession = Depends(db_session),
):
    try:
        category_service = CategoryService(session)
        collections = (
            await category_service.get_all_collections_belongs_to_all_categories()
        )

        payload = CommonResponse(
            success=True,
            message="All collections fetched successfully",
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
            message="Error while fetching all collections belongs to all categories",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get("/{category_id}", name="Get a category by ID")
async def get_category_by_id(
    response: Response,
    category_id: UUID4 = Path(..., title="The ID of the category to fetch"),
    session: AsyncSession = Depends(db_session),
):

    try:
        category_service = CategoryService(session)
        category = await category_service.get_category_by_id(category_id)

        payload = CommonResponse(
            success=True, message="Category fetched successfully", payload=category
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


@router.post("", name="Create a category")
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

        category_data = CreateCategory(
            name=name,
            description=description,
            collection_ids=collection_ids,
            order_seq=order_seq,
        )
        category_service = CategoryService(session)
        category_record = await category_service.create_category(
            cover_image_file, category_data
        )
        payload = CommonResponse(
            success=True,
            message="category created successfully",
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
            success=False, message="Error creating category", payload=str(e)
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.patch("/{category_id}", name="Update a category")
async def update_category(
    response: Response,
    category_id: UUID4 = Path(..., title="The ID of the category to update"),
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

        category_service = CategoryService(session)
        category_data = UpdateCategory(
            name=name,
            description=description,
            order_seq=order_seq,
            collection_ids=collection_ids,
        )
        updated_category = await category_service.update_category(
            category_id, cover_image_file, category_data
        )
        payload = CommonResponse(
            success=True,
            message="Category updated successfully",
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
            success=False, message="Error updating category", payload=str(e)
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.delete("/{category_id}", name="Delete the category")
async def delete_category(
    response: Response,
    category_id: UUID4 = Path(..., title="The ID of the category to delete"),
    session: AsyncSession = Depends(db_session),
):

    try:

        category_service = CategoryService(session)
        await category_service.delete_category(category_id)
        payload = CommonResponse(
            success=True, message="Category deleted successfully", payload=None
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
            success=False, message="Error while deleting the category", payload=str(e)
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


# get all collections belongs to a category
@router.get(
    "/{category_id}/collections", name="Get all the collections belongs to a category"
)
async def get_all_collections_belongs_to_category(
    response: Response,
    category_id: UUID4 = Path(..., title="The ID of the category to fetch"),
    session: AsyncSession = Depends(db_session),
):
    try:
        category_service = CategoryService(session)
        collections = await category_service.get_collections_by_category(category_id)

        payload = CommonResponse(
            success=True,
            message="Collections fetched successfully",
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
            message="Error while fetching collections belongs to a category",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get(
    "/{category_id}/randomized/tracks/{track_count}",
    name="Generate random track list based on category id",
)
async def generate_random_track_list(
    response: Response,
    category_id: UUID4 = Path(..., title="The ID of the category to fetch"),
    track_count: int = Path(..., title="Numbers of track count to generate"),
    session: AsyncSession = Depends(db_session),
):

    try:
        category_service = CategoryService(session)
        tracks = await category_service.get_random_tracks_based_on_category(
            category_id, track_count
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
