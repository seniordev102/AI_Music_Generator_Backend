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

from app.api.collection.service import CollectionService
from app.api.oracle.service import OracleService
from app.api.track.bulk_upload_service import BulkTrackUploadService
from app.api.track.service import TrackService
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.models import Track
from app.schemas import CreateTrack, GetTrackIds, UpdateTrack

router = APIRouter()

task_cache = {}


@router.get("", name="Get all the tracks")
async def get_tracks(
    response: Response,
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=0),
    search: Optional[str] = Query(
        None,
        description="Search in name, description, frequency, frequency_meaning, upright_message",
    ),
    is_lyrical: Optional[bool] = Query(None, description="Filter by is_lyrical"),
    is_hidden: Optional[bool] = Query(None, description="Filter by is_hidden"),
    is_private: Optional[bool] = Query(None, description="Filter by is_private"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    sort_by: Optional[str] = Query(
        "created_at", description="Sort by field (created_at or updated_at)"
    ),
    sort_order: Optional[str] = Query("desc", description="Sort order (asc or desc)"),
    session: AsyncSession = Depends(db_session),
):

    try:
        track_service = TrackService(session)
        tracks, page_meta = await track_service.get_all_tracks(
            page=page,
            page_size=per_page,
            search=search,
            is_lyrical=is_lyrical,
            is_hidden=is_hidden,
            is_private=is_private,
            status_filter=status_filter,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        payload = CommonResponse[List[Track]](
            message="Successfully fetched all tracks",
            success=True,
            payload=tracks,
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


@router.get("/{track_id}", name="Get a track by id")
async def get_track_by_id(
    response: Response,
    track_id: UUID4 = Path(..., title="The ID of the track to fetch"),
    session: AsyncSession = Depends(db_session),
):

    try:
        track_service = TrackService(session)
        track = await track_service.get_track_by_id(track_id)
        payload = CommonResponse(
            message="Successfully fetched track",
            success=True,
            payload=track,
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
    "/with-collection/{track_id}",
    name="Get a track details with collection details by id",
)
async def get_track_by_id(
    response: Response,
    track_id: UUID4 = Path(..., title="The ID of the track to fetch"),
    session: AsyncSession = Depends(db_session),
):

    try:
        track_service = TrackService(session)
        track = await track_service.get_track__with_collection(track_id)
        payload = CommonResponse(
            message="Successfully fetched track",
            success=True,
            payload=track,
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


@router.post(
    "/get-tracks-by-ids",
    name="Get track details with collections by track ids",
)
async def get_tracks_by_ids(
    response: Response,
    payload: GetTrackIds,
    session: AsyncSession = Depends(db_session),
):

    try:
        track_service = TrackService(session)
        track = await track_service.get_tracks_with_collections_by_ids_no_safe_check(
            track_ids=payload.track_ids
        )
        payload = CommonResponse(
            message="Successfully fetched all tracks by ids",
            success=True,
            payload=track,
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


@router.post("", name="Create a track")
async def create_track(
    response: Response,
    track_data: CreateTrack = Depends(CreateTrack.parse_track_data),
    session: AsyncSession = Depends(db_session),
):

    try:
        # validate file types
        collection_service = CollectionService(session)
        await collection_service.get_collection_by_id(track_data.collection_id)

        # Create track
        track_service = TrackService(session)
        track = await track_service.create_track(track_data)
        payload = CommonResponse(
            success=True, message="Track created successfully", payload=track
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
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.patch("/{track_id}", name="Update a track")
async def update_track(
    response: Response,
    track_id: UUID4,
    name: Optional[str] = Form(None),
    collection_id: Optional[UUID4] = Form(None),
    cover_image_file: Optional[UploadFile] = File(None),
    instrumental_audio_file: Optional[UploadFile] = File(None),
    upright_audio_file: Optional[UploadFile] = File(None),
    reverse_audio_file: Optional[UploadFile] = File(None),
    hires_audio_file: Optional[UploadFile] = File(None),
    user_id: Optional[UUID4] = Form(None),
    upright_message: Optional[str] = Form(None),
    reverse_message: Optional[str] = Form(None),
    frequency: Optional[str] = Form(None),
    frequency_meaning: Optional[str] = Form(None),
    track_metadata: Optional[str] = Form(None),
    crafted_by: Optional[str] = Form(None),
    session: AsyncSession = Depends(db_session),
):

    try:
        track_service = TrackService(session)
        existing_track = await track_service.get_track_by_id(track_id)

        # validate the track file
        if not existing_track:
            payload = CommonResponse(
                success=False, message="Track not found", payload=None
            )
            response.status_code = status.HTTP_404_NOT_FOUND
            return payload

        # validate album id
        if collection_id:
            collection_service = CollectionService(session)
            await collection_service.get_collection_by_id(collection_id)

        # update track
        update_track_data = UpdateTrack(
            name=name,
            collection_id=collection_id,
            user_id=user_id,
            upright_message=upright_message,
            reverse_message=reverse_message,
            frequency=frequency,
            frequency_meaning=frequency_meaning,
            track_metadata=track_metadata,
            crafted_by=crafted_by,
        )

        updated_track = await track_service.update_track(
            track_id=track_id,
            track_data=update_track_data,
            cover_image_file=cover_image_file,
            instrumental_audio_file=instrumental_audio_file,
            upright_audio_file=upright_audio_file,
            reverse_audio_file=reverse_audio_file,
            hires_audio_file=hires_audio_file,
        )

        if not updated_track:
            payload = CommonResponse(
                success=False, message="Failed to update track", payload=None
            )
            response.status_code = status.HTTP_400_BAD_REQUEST
            return payload

        payload = CommonResponse(
            success=True, message="Track updated successfully", payload=updated_track
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


# delete a track
@router.delete("/{track_id}", name="Delete a track")
async def delete_track(
    response: Response,
    track_id: UUID4 = Path(..., title="The ID of the Track to delete"),
    session: AsyncSession = Depends(db_session),
):
    try:
        track_service = TrackService(session)
        is_deleted = await track_service.delete_track(track_id)

        if not is_deleted:
            payload = CommonResponse(
                success=False, message="Something when wrong", payload=None
            )
            response.status_code = status.HTTP_400_BAD_REQUEST
            return payload

        payload = CommonResponse(
            success=True, message="Track deleted successfully", payload=None
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


# delete all tracks in a collection
@router.delete("/delete-all/{collection_id}", name="Delete all tracks in a collection")
async def delete_all_tracks(
    response: Response,
    collection_id: UUID4 = Path(..., title="The ID of the collection"),
    session: AsyncSession = Depends(db_session),
):
    try:
        track_service = TrackService(session)
        is_deleted = await track_service.delete_all_tracks_by_collection_id(
            collection_id
        )

        if not is_deleted:
            payload = CommonResponse(
                success=False, message="Something when wrong", payload=None
            )
            response.status_code = status.HTTP_400_BAD_REQUEST
            return payload

        payload = CommonResponse(
            success=True, message="All Tracks deleted successfully", payload=None
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


@router.post("/bulk-upload")
async def bulk_upload(
    response: Response,
    background_tasks: BackgroundTasks,
    collection_id: UUID4 = Form(...),
    user_id: Optional[UUID4] = Form(None),
    names: List[str] = Form(...),
    descriptions: List[Optional[str]] = Form(...),
    short_description: List[Optional[str]] = Form(None),
    mp3_files: List[UploadFile] = File(...),
    hi_res_files: List[UploadFile] = File(...),
    cover_images: List[UploadFile] = File(...),
    session: AsyncSession = Depends(db_session),
):

    # Validate that all lists are of the same length
    lengths = {
        len(names),
        len(mp3_files),
        len(hi_res_files),
        len(cover_images),
        len(descriptions),
    }
    if len(lengths) > 1:
        payload = CommonResponse(
            success=False, message="All lists must have the same length", payload=None
        )
        response.status_code = status.HTTP_400_BAD_REQUEST
        return payload

    # Prepare the data for the background task
    track_list = []
    for i in range(len(names)):
        mp3_file_content = await mp3_files[i].read()
        hi_res_file_content = await hi_res_files[i].read()
        cover_image_content = await cover_images[i].read()
        mp3_file_name = mp3_files[i].filename
        hi_res_file_name = hi_res_files[i].filename
        cover_image_name = cover_images[i].filename
        mp3_file_content_type = mp3_files[i].content_type
        hi_res_file_content_type = hi_res_files[i].content_type
        cover_image_content_type = cover_images[i].content_type
        track_description = descriptions[i] if descriptions[i] else None
        track_short_description = None
        if short_description:
            track_short_description = short_description[i]
        track_name = names[i]
        track_list.append(
            (
                mp3_file_content,
                hi_res_file_content,
                cover_image_content,
                track_description,
                track_short_description,
                track_name,
                mp3_file_name,
                hi_res_file_name,
                cover_image_name,
                mp3_file_content_type,
                hi_res_file_content_type,
                cover_image_content_type,
            )
        )

    task_id = str(uuid.uuid4())
    background_tasks.add_task(
        TrackService.bulk_create_tracks,
        track_list=track_list,
        task_id=task_id,
        cache=task_cache,
        collection_id=collection_id,
        user_id=user_id,
        session=session,
    )

    payload = CommonResponse(
        success=True, message="task started ", payload={"task_id": task_id}
    )
    response.status_code = status.HTTP_200_OK
    return payload


@router.get("/task-progress/{task_id}")
def get_task_progress(response: Response, task_id: str):
    task_details = task_cache.get(task_id, {"status": "unknown"})
    payload = CommonResponse(
        success=True, message="task started ", payload=task_details
    )
    response.status_code = status.HTTP_200_OK
    return payload


@router.get("/randomized/{track_count}", name="Generate random track list")
async def generate_random_track_list(
    response: Response,
    track_count: int = Path(..., title="Numbers of track count to generate"),
    session: AsyncSession = Depends(db_session),
):

    try:
        track_service = TrackService(session)
        tracks = await track_service.generate_random_track_list(track_count)
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


@router.get("/search/list", name="Search tracks")
async def search_tracks(
    response: Response,
    query: str = Query(None, title="Search Query"),
    session: AsyncSession = Depends(db_session),
):
    try:
        track_service = TrackService(session)
        tracks = await track_service.search_tracks(query)
        payload = CommonResponse(
            message="Successfully fetched search results",
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


@router.post("/ai-generate/ten-spread", name="Generate ai based ten track spread")
async def search_tracks(
    response: Response,
    body: dict = Body(...),
    session: AsyncSession = Depends(db_session),
):
    try:
        user_prompt = body.get("user_prompt")
        track_service = TrackService(session)
        oracle_service = OracleService(session)

        # get the track ids
        track_ids = (
            await oracle_service.retrieve_related_tracks_based_on_prompt_using_pgvector(
                user_prompt
            )
        )
        tracks = await track_service.get_track_data_from_ids(track_ids)
        random.shuffle(tracks)
        payload = CommonResponse(
            message="Successfully fetched tracks for user query",
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


@router.post("/ai-generate/album-cover", name="Generate ai based album cover")
async def search_tracks(
    response: Response,
    body: dict = Body(...),
    session: AsyncSession = Depends(db_session),
):
    try:
        user_prompt = body.get("user_prompt")
        oracle_service = OracleService(session)
        image_url = await oracle_service.generate_album_art_based_on_prompt(user_prompt)

        payload = CommonResponse(
            message="Successfully generate ai art",
            success=True,
            payload=image_url,
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


@router.post("/ai-generate/square-album-cover", name="Generate ai based album cover")
async def search_tracks(
    response: Response,
    body: dict = Body(...),
    session: AsyncSession = Depends(db_session),
):
    try:
        user_prompt = body.get("user_prompt")
        oracle_service = OracleService(session)
        image_url = await oracle_service.generate_square_album_art_based_on_prompt(
            user_prompt
        )

        payload = CommonResponse(
            message="Successfully generate ai art",
            success=True,
            payload=image_url,
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


@router.post("/v2", name="Create a track")
async def create_track_new(
    response: Response,
    background_tasks: BackgroundTasks,
    track_data: CreateTrack = Depends(CreateTrack.parse_track_data),
    session: AsyncSession = Depends(db_session),
):
    try:
        # 1. Quick validation first before heavy processing
        if not await BulkTrackUploadService.validate_files_basic(track_data):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file format"
            )

        # 2. Validate collection exists
        collection_service = CollectionService(session)
        collection = await collection_service.get_collection_by_id(
            track_data.collection_id
        )

        # 3. Create track service
        track_service = BulkTrackUploadService(session)

        # 4. Create initial track record
        track = await track_service.create_initial_track(
            name=track_data.name,
            collection_id=track_data.collection_id,
            user_id=track_data.user_id,
            is_hidden=collection.is_hidden,
            is_private=collection.is_private,
            frequency=track_data.frequency,
            frequency_meaning=track_data.frequency_meaning,
            upright_message=track_data.upright_message,
            reverse_message=track_data.reverse_message,
            crafted_by=track_data.crafted_by,
        )

        # 5. Process files in background
        background_tasks.add_task(
            track_service.process_track_files, track_id=track.id, track_data=track_data
        )

        payload = CommonResponse(
            success=True,
            message="Track creation initiated. Files are being processed.",
            payload={"track_id": track.id},
        )
        response.status_code = status.HTTP_202_ACCEPTED
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
