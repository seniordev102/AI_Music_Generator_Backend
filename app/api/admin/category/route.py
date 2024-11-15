from fastapi import APIRouter, Body, Depends, HTTPException, Path, status
from fastapi.responses import Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.admin.category.service import CategoryManageService
from app.auth.auth_handler import AuthHandler
from app.common.http_response_model import CommonResponse
from app.database import db_session
from app.models import ExcludeCategoriesType
from app.schemas import CreateExcludeCategory

router = APIRouter()


# get exclude categories by type
@router.get("/exclude-categories/{exclude_type}", name="Get exclude categories by type")
async def get_exclude_categories_by_type(
    response: Response,
    email: str = Depends(AuthHandler()),
    exclude_type: ExcludeCategoriesType = Path(..., title="Exclude category type"),
    session: AsyncSession = Depends(db_session),
):

    try:
        category_service = CategoryManageService(session)
        result = await category_service.get_exclude_categories_by_type_service(
            exclude_type=exclude_type
        )
        payload = CommonResponse(
            message="Successfully fetch exclude categories by type.",
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


@router.post("/exclude-categories", name="Exclude categories from iah products")
async def exclude_categories_from_iah_products(
    response: Response,
    email: str = Depends(AuthHandler()),
    request: CreateExcludeCategory = Body(...),
    session: AsyncSession = Depends(db_session),
):

    try:
        category_service = CategoryManageService(session)
        result = await category_service.exclude_categories_from_iah_service(
            data=request
        )
        payload = CommonResponse(
            message="Successfully excluded categories from IAH products.",
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
