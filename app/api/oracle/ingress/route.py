from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.oracle.ingress.service import IngressService
from app.auth.auth_handler import AuthHandler
from app.common.http_response_model import CommonResponse
from app.database import db_session

router = APIRouter()


@router.get("/tracks", name="Index all the tracks to vector database")
async def index_tracks_to_vector_database(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        ingress_service = IngressService(session)
        result = await ingress_service.index_tracks_to_pgvector_database()
        payload = CommonResponse(
            success=True,
            message="All tracks has been indexed to vector database",
            payload=result,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        print(http_err)
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        print(e)
        payload = CommonResponse(
            success=False,
            message="Error while indexing tracks to vector database",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get("/collections", name="Index all the collections to vector database")
async def index_collections_to_vector_database(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        ingress_service = IngressService(session)
        result = await ingress_service.index_collections_to_pgvector_database()
        payload = CommonResponse(
            success=True,
            message="All collections has been indexed to vector database",
            payload=result,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        print(http_err)
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        print(e)
        payload = CommonResponse(
            success=False,
            message="Error while indexing collections to vector database",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get(
    "/tracks/all/generate-ai-summary", name="Regenerate AI summary for all tracks"
)
async def index_tracks_to_vector_database(
    response: Response,
    background_tasks: BackgroundTasks,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        ingress_service = IngressService(session)
        result = await ingress_service.generate_ai_summary_for_all_tracks(
            background_tasks
        )
        payload = CommonResponse(
            success=True, message="AI summary generated", payload=result
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        print(http_err)
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        print(e)
        payload = CommonResponse(
            success=False,
            message="Error while generating metadata for user prompt",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get(
    "/tracks/batch/generate-ai-summary",
    name="Regenerate AI summary for all tracks as a batch job",
)
async def index_tracks_to_vector_database(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        ingress_service = IngressService(session)
        result = await ingress_service.generate_ai_summary_as_batch()
        payload = CommonResponse(
            success=True, message="AI summary generated", payload=result
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        print(http_err)
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        print(e)
        payload = CommonResponse(
            success=False,
            message="Error while generating metadata for user prompt",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get(
    "/tracks/sync/generate-ai-summary",
    name="Regenerate AI summary for missing tracks",
)
async def generate_ai_summary_for_missing_tracks(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        ingress_service = IngressService(session)
        result = await ingress_service.generate_ai_summary_for_missing_tracks()
        payload = CommonResponse(
            success=True, message="AI summary generated", payload=result
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        print(http_err)
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        print(e)
        payload = CommonResponse(
            success=False,
            message="Error while generating metadata for user prompt",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get(
    "/update/vector-index",
    name="Update all the index with missing ones",
)
async def update_vector_indexes(
    response: Response,
    session: AsyncSession = Depends(db_session),
):

    try:
        ingress_service = IngressService(session)
        result = await ingress_service.update_vector_indexes()
        payload = CommonResponse(
            success=True, message="All indexes has been updated", payload=result
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        print(http_err)
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        print(e)
        payload = CommonResponse(
            success=False,
            message="Error while updating indexes",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get(
    "/index/status",
    name="Get all the index details",
)
async def get_index_details_status(
    response: Response,
    session: AsyncSession = Depends(db_session),
):

    try:
        ingress_service = IngressService(session)
        result = await ingress_service.get_vector_data_index_status()
        payload = CommonResponse(
            success=True, message="All indexes has been updated", payload=result
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        print(http_err)
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        print(e)
        payload = CommonResponse(
            success=False,
            message="Error while updating indexes",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get(
    "/index/sync-status",
    name="Get all the index sync status",
)
async def get_track_sync_status(
    response: Response,
    session: AsyncSession = Depends(db_session),
):

    try:
        ingress_service = IngressService(session)
        result = await ingress_service.get_vector_db_sync_status()
        payload = CommonResponse(
            success=True,
            message="Vector DB track sync index details fetched",
            payload=result,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        print(http_err)
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        print(e)
        payload = CommonResponse(
            success=False,
            message="Error while updating indexes",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get(
    "/index/resync-tracks",
    name="Update the status of track embedding table remove hidden track and add missing indexes",
)
async def resync_track_embedding(
    response: Response,
    session: AsyncSession = Depends(db_session),
):

    try:
        ingress_service = IngressService(session)
        result = await ingress_service.resync_track_vector_indexes()
        payload = CommonResponse(
            success=True,
            message="Track vector indexes has been updated and resync",
            payload=result,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        print(http_err)
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        print(e)
        payload = CommonResponse(
            success=False,
            message="Error while updating indexes",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get(
    "/index/resync-collections",
    name="Update the status of collection embedding table remove hidden collection and add missing indexes",
)
async def resync_track_embedding(
    response: Response,
    session: AsyncSession = Depends(db_session),
):

    try:
        ingress_service = IngressService(session)
        result = await ingress_service.resync_collection_vector_indexes()
        payload = CommonResponse(
            success=True,
            message="Collection vector indexes has been updated and resync",
            payload=result,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        print(http_err)
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        print(e)
        payload = CommonResponse(
            success=False,
            message="Error while updating indexes",
            payload=str(e),
        )
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload
