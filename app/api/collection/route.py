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

from app.api.collection.service import CollectionService
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.models import Collection
from app.schemas import CreateCollection, UpdateCollection

router = APIRouter()


@router.get("", name="Get all collections")
async def get_collections(
    response: Response,
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=0),
    session: AsyncSession = Depends(db_session),
):

    try:
        collection_service = CollectionService(session)
        collections, page_meta = await collection_service.get_all_collections(
            page, per_page
        )
        payload = CommonResponse[List[Collection]](
            message="Successfully fetched collections",
            success=True,
            payload=collections,
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


@router.get("/home-page", name="Get all collections with one track for home page")
async def get_collections_with_track(
    response: Response,
    session: AsyncSession = Depends(db_session),
):

    try:
        collection_service = CollectionService(session)
        collections = await collection_service.get_all_collections_with_one_track()
        payload = CommonResponse(
            message="Successfully fetched collections",
            success=True,
            payload=collections,
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


@router.get("/admin", name="Get all collections for admin")
async def get_collections(
    response: Response,
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=0),
    session: AsyncSession = Depends(db_session),
):

    try:
        collection_service = CollectionService(session)
        collections, page_meta = await collection_service.get_all_collections_for_admin(
            page, per_page
        )
        payload = CommonResponse[List[Collection]](
            message="Successfully fetched collections",
            success=True,
            payload=collections,
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


@router.get("/{collection_id}", name="Get a collection")
async def get_collection_by_id(
    response: Response,
    collection_id: UUID4 = Path(..., title="The ID of the collection to fetch"),
    session: AsyncSession = Depends(db_session),
):

    try:
        collection_service = CollectionService(session)
        collection = await collection_service.get_collection_by_id(collection_id)

        payload = CommonResponse(
            success=True, message="Collection fetched successfully", payload=collection
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


@router.post("", name="Create a collection")
async def create_collection(
    response: Response,
    cover_image_file: UploadFile = File(
        None, title="The cover image file of the collection"
    ),
    square_cover_image_file: UploadFile = File(
        None, title="The square cover image file of the collection"
    ),
    name: str = Form(..., title="The name of the collection"),
    user_id: UUID4 = Form(None, title="The ID of the user who created the collection"),
    description: str = Form(None, title="The description of the collection"),
    short_description: str = Form(
        None, title="The short description of the collection"
    ),
    audience: str = Form(None, title="The audience of the collection"),
    frequency: str = Form(None, title="The frequency of the collection"),
    genre: str = Form(None, title="The genre of the collection"),
    lead_producer: str = Form(None, title="The lead producer of the collection"),
    chakra: str = Form(None, title="The chakra of the collection"),
    order_seq: int = Form(None, title="The order sequence of the collection"),
    is_private: bool = Form(False, title="Boolean value to edit collection visibility"),
    is_hidden: bool = Form(False, title="Boolean value to edit collection visibility"),
    is_delist: bool = Form(
        False, title="Boolean value to edit collection listing visibility"
    ),
    is_iah_radio: bool = Form(
        False, title="Boolean value to select collection as IAH Radio"
    ),
    crafted_by: str = Form(None, title="The crafted by of the collection"),
    session: AsyncSession = Depends(db_session),
):

    try:

        collection_data = CreateCollection(
            name=name,
            user_id=user_id,
            description=description,
            short_description=short_description,
            audience=audience,
            frequency=frequency,
            genre=genre,
            lead_producer=lead_producer,
            chakra=chakra,
            order_seq=order_seq,
            is_hidden=is_hidden,
            is_private=is_private,
            is_delist=is_delist,
            is_iah_radio=is_iah_radio,
            crafted_by=crafted_by,
        )
        collection_service = CollectionService(session)
        created_collection = await collection_service.create_collection(
            cover_image_file, square_cover_image_file, collection_data
        )
        payload = CommonResponse(
            success=True,
            message="Collection created successfully",
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
            success=False, message="Error creating album", payload=str(e)
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.patch("/{collection_id}", name="Update a collection")
async def update_collection(
    response: Response,
    collection_id: UUID4 = Path(..., title="The ID of the collection to update"),
    cover_image_file: UploadFile = File(
        None, title="The cover image file of the collection"
    ),
    square_cover_image_file: UploadFile = File(
        None, title="The square cover image file of the collection"
    ),
    name: str = Form(None, title="The name of the collection"),
    user_id: UUID4 = Form(None, title="The ID of the user who created the collection"),
    description: str = Form(None, title="The description of the collection"),
    short_description: str = Form(
        None, title="The short description of the collection"
    ),
    audience: str = Form(None, title="The audience of the collection"),
    order_seq: int = Form(None, title="The order sequence of the collection"),
    frequency: str = Form(None, title="The frequency of the collection"),
    genre: str = Form(None, title="The genre of the collection"),
    lead_producer: str = Form(None, title="The lead producer of the collection"),
    is_private: bool = Form(None, title="Boolean value to edit collection visibility"),
    is_hidden: bool = Form(None, title="Boolean value to edit collection visibility"),
    is_delist: bool = Form(
        None, title="Boolean value to edit collection listing visibility"
    ),
    is_iah_radio: bool = Form(
        None, title="Boolean value to select collection as IAH Radio"
    ),
    crafted_by: str = Form(None, title="The crafted by of the collection"),
    session: AsyncSession = Depends(db_session),
):

    try:

        collection_service = CollectionService(session)
        collection_update_data = UpdateCollection(
            name=name,
            user_id=user_id,
            description=description,
            short_description=short_description,
            order_seq=order_seq,
            audience=audience,
            frequency=frequency,
            genre=genre,
            lead_producer=lead_producer,
            is_hidden=is_hidden,
            is_private=is_private,
            is_delist=is_delist,
            is_iah_radio=is_iah_radio,
            crafted_by=crafted_by,
        )
        updated_collection = await collection_service.update_collection(
            collection_id,
            collection_update_data,
            cover_image_file,
            square_cover_image_file,
        )
        payload = CommonResponse(
            success=True,
            message="Collection updated successfully",
            payload=updated_collection,
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


@router.delete("/{collection_id}", name="Delete collection")
async def delete_collection(
    response: Response,
    collection_id: UUID4 = Path(..., title="The ID of the collection to delete"),
    session: AsyncSession = Depends(db_session),
):

    try:

        collection_service = CollectionService(session)
        await collection_service.delete_collection(collection_id)
        payload = CommonResponse(
            success=True, message="Collection deleted successfully", payload=None
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


# get tracks belongs to a collection
@router.get("/{collection_id}/tracks", name="Get all the tracks of a collection")
async def get_tracks_belongs_to_album(
    response: Response,
    collection_id: UUID4 = Path(..., title="The ID of the collection to fetch"),
    session: AsyncSession = Depends(db_session),
):
    try:
        collection_service = CollectionService(session)
        collection = await collection_service.get_collection_by_id(collection_id)

        #  get all tracks of an album
        tracks = await collection_service.get_tracks_of_collection(collection_id)

        payload_data = {"collection": collection, "tracks": tracks}

        payload = CommonResponse(
            success=True,
            message="Collection and tracks details fetched successfully",
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


@router.get("/search/list", name="Search collections")
async def search_collections(
    response: Response,
    query: str = Query(None, title="Search Query"),
    session: AsyncSession = Depends(db_session),
):
    try:
        collection_service = CollectionService(session)
        collections = await collection_service.search_collections(query)
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
