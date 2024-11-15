from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.credit_management.monthly_allocation.discrepancy_service import (
    DiscrepancyDetectionService,
)
from app.api.credit_management.monthly_allocation.retry_service import (
    AllocationRetryService,
)
from app.api.credit_management.monthly_allocation.scheduler import (
    MonthlyAllocationScheduler,
)
from app.api.credit_management.monthly_allocation.service import (
    MonthlyCreditAllocationService,
)
from app.api.deps import get_current_admin_user, get_db
from app.common.http_response_model import CommonResponse, PageMeta
from app.models import AllocationDiscrepancy, FailedAllocation, UserSubscription

router = APIRouter(prefix="/monthly-allocations", tags=["Monthly Allocations"])


@router.post("/run")
async def run_monthly_allocations(
    response: Response,
    auto_fix: bool = Query(
        False, description="Enable automatic fixing of discrepancies"
    ),
    db: AsyncSession = Depends(get_db),
    _: Dict = Depends(get_current_admin_user),
) -> CommonResponse:
    """
    Run the monthly allocation process.

    This endpoint triggers:
    1. Allocation of credits for eligible subscriptions
    2. Retry of failed allocations
    3. Detection and fixing of discrepancies
    4. Update of next allocation dates

    Only accessible to admin users.
    """
    try:
        scheduler = MonthlyAllocationScheduler(db, auto_fix_enabled=auto_fix)
        results = await scheduler.run_monthly_allocations()

        # Update next allocation dates
        updated_next_dates = await scheduler.update_next_allocation_dates()
        results["updated_next_dates"] = updated_next_dates

        payload = CommonResponse(
            message="Monthly allocation process completed successfully",
            success=True,
            payload=results,
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


@router.get("/subscriptions/eligible")
async def get_eligible_subscriptions(
    response: Response,
    db: AsyncSession = Depends(get_db),
    _: Dict = Depends(get_current_admin_user),
) -> CommonResponse:
    """
    Get all subscriptions eligible for monthly credit allocation.

    Only accessible to admin users.
    """
    try:
        service = MonthlyCreditAllocationService(db)
        eligible_subscriptions = await service._get_eligible_subscriptions()

        formatted_subscriptions = [
            {
                "id": str(sub.id),
                "user_id": str(sub.user_id),
                "package_id": str(sub.package_id),
                "status": sub.status,
                "billing_cycle": sub.billing_cycle,
                "credit_allocation_cycle": sub.credit_allocation_cycle,
                "last_credit_allocation_date": sub.last_credit_allocation_date,
                "next_credit_allocation_date": sub.next_credit_allocation_date,
            }
            for sub in eligible_subscriptions
        ]

        payload = CommonResponse(
            message="Eligible subscriptions fetched successfully",
            success=True,
            payload=formatted_subscriptions,
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


@router.post("/subscriptions/{subscription_id}/allocate")
async def allocate_credits_for_subscription(
    response: Response,
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Dict = Depends(get_current_admin_user),
) -> CommonResponse:
    """
    Manually allocate credits for a specific subscription.

    Only accessible to admin users.
    """
    try:
        # Get subscription
        subscription = await db.get(UserSubscription, subscription_id)
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subscription with ID {subscription_id} not found",
            )

        # Check if subscription is eligible
        if subscription.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Subscription is not active (status: {subscription.status})",
            )

        if (
            subscription.billing_cycle != "yearly"
            or subscription.credit_allocation_cycle != "monthly"
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Subscription is not eligible for monthly allocation (billing_cycle: {subscription.billing_cycle}, allocation_cycle: {subscription.credit_allocation_cycle})",
            )

        # Allocate credits
        service = MonthlyCreditAllocationService(db)
        result = await service.allocate_monthly_credits(subscription)

        payload = CommonResponse(
            message="Credits allocated successfully for subscription",
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


@router.get("/failed")
async def get_failed_allocations(
    response: Response,
    status_filter: Optional[str] = Query(
        None, description="Filter by status (pending_retry, failed)", alias="status"
    ),
    limit: int = Query(100, description="Maximum number of records to return"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    _: Dict = Depends(get_current_admin_user),
) -> CommonResponse:
    """
    Get failed allocations.

    Only accessible to admin users.
    """
    try:
        # Calculate pagination
        skip = (page - 1) * page_size

        # Build query
        query = select(FailedAllocation).order_by(desc(FailedAllocation.created_at))

        # Apply filters
        if status_filter:
            query = query.where(FailedAllocation.status == status_filter)

        # Get total count
        count_query = select(FailedAllocation)
        if status_filter:
            count_query = count_query.where(FailedAllocation.status == status_filter)

        count_result = await db.execute(count_query)
        total_items = len(count_result.scalars().all())

        # Apply pagination
        query = query.offset(skip).limit(page_size)

        # Execute query
        result = await db.execute(query)
        failed_allocations = result.scalars().all()

        # Format results
        formatted_allocations = [
            {
                "id": str(fa.id),
                "subscription_id": str(fa.subscription_id),
                "user_id": str(fa.user_id),
                "error_message": fa.error_message,
                "retry_count": fa.retry_count,
                "status": fa.status,
                "next_retry_at": fa.next_retry_at,
                "created_at": fa.created_at,
                "resolved_at": fa.resolved_at,
                "resolution_notes": fa.resolution_notes,
            }
            for fa in failed_allocations
        ]

        # Create pagination metadata
        total_pages = (total_items + page_size - 1) // page_size
        pagination = PageMeta(
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            total_items=total_items,
        )

        payload = CommonResponse(
            message="Failed allocations fetched successfully",
            success=True,
            payload=formatted_allocations,
            meta=pagination,
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


@router.post("/failed/{failed_allocation_id}/retry")
async def retry_failed_allocation(
    response: Response,
    failed_allocation_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Dict = Depends(get_current_admin_user),
) -> CommonResponse:
    """
    Manually retry a failed allocation.

    Only accessible to admin users.
    """
    try:
        # Get failed allocation
        failed_allocation = await db.get(FailedAllocation, failed_allocation_id)
        if not failed_allocation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Failed allocation with ID {failed_allocation_id} not found",
            )

        # Check if already resolved
        if failed_allocation.status not in ["pending_retry", "failed"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed allocation is already {failed_allocation.status}",
            )

        # Get subscription
        subscription = await db.get(UserSubscription, failed_allocation.subscription_id)
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subscription with ID {failed_allocation.subscription_id} not found",
            )

        # Retry allocation
        service = MonthlyCreditAllocationService(db)
        result = await service.allocate_monthly_credits(subscription)

        # Update failed allocation if successful
        if result["status"] == "success":
            failed_allocation.status = "resolved"
            failed_allocation.resolution_notes = f"Manually retried and succeeded. Transaction ID: {result['transaction_id']}"
            failed_allocation.resolved_at = datetime.now(timezone.utc)
            db.add(failed_allocation)
            await db.commit()

        payload = CommonResponse(
            message="Failed allocation retry processed successfully",
            success=True,
            payload={
                "failed_allocation_id": str(failed_allocation_id),
                "result": result,
            },
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


@router.get("/discrepancies")
async def get_discrepancies(
    response: Response,
    status_filter: Optional[str] = Query(
        None,
        description="Filter by status (detected, fixed, fix_failed)",
        alias="status",
    ),
    limit: int = Query(100, description="Maximum number of records to return"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    _: Dict = Depends(get_current_admin_user),
) -> CommonResponse:
    """
    Get allocation discrepancies.

    Only accessible to admin users.
    """
    try:
        # Calculate pagination
        skip = (page - 1) * page_size

        # Build query
        query = select(AllocationDiscrepancy).order_by(
            desc(AllocationDiscrepancy.created_at)
        )

        # Apply filters
        if status_filter:
            query = query.where(AllocationDiscrepancy.status == status_filter)

        # Get total count
        count_query = select(AllocationDiscrepancy)
        if status_filter:
            count_query = count_query.where(
                AllocationDiscrepancy.status == status_filter
            )

        count_result = await db.execute(count_query)
        total_items = len(count_result.scalars().all())

        # Apply pagination
        query = query.offset(skip).limit(page_size)

        # Execute query
        result = await db.execute(query)
        discrepancies = result.scalars().all()

        # Format results
        formatted_discrepancies = [
            {
                "id": str(d.id),
                "subscription_id": str(d.subscription_id),
                "user_id": str(d.user_id),
                "discrepancy_type": d.discrepancy_type,
                "allocation_period": d.allocation_period,
                "expected_amount": d.expected_amount,
                "actual_amount": d.actual_amount,
                "status": d.status,
                "created_at": d.created_at,
                "resolved_at": d.resolved_at,
                "resolution_notes": d.resolution_notes,
            }
            for d in discrepancies
        ]

        # Create pagination metadata
        total_pages = (total_items + page_size - 1) // page_size
        pagination = PageMeta(
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            total_items=total_items,
        )

        payload = CommonResponse(
            message="Discrepancies fetched successfully",
            success=True,
            payload=formatted_discrepancies,
            meta=pagination,
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


@router.post("/discrepancies/{discrepancy_id}/fix")
async def fix_discrepancy(
    response: Response,
    discrepancy_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: Dict = Depends(get_current_admin_user),
) -> CommonResponse:
    """
    Manually fix a discrepancy.

    Only accessible to admin users.
    """
    try:
        # Get discrepancy
        discrepancy = await db.get(AllocationDiscrepancy, discrepancy_id)
        if not discrepancy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Discrepancy with ID {discrepancy_id} not found",
            )

        # Check if already fixed
        if discrepancy.status != "detected":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Discrepancy is already {discrepancy.status}",
            )

        # Get subscription
        subscription = await db.get(UserSubscription, discrepancy.subscription_id)
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subscription with ID {discrepancy.subscription_id} not found",
            )

        # Fix discrepancy
        service = DiscrepancyDetectionService(db, auto_fix_enabled=True)

        if discrepancy.discrepancy_type == "missing_allocation":
            discrepancy_data = {
                "type": "missing_allocation",
                "period": discrepancy.allocation_period,
                "expected_amount": discrepancy.expected_amount,
                "actual_amount": discrepancy.actual_amount,
            }
            result = await service._fix_missing_allocation(
                subscription, discrepancy_data, discrepancy.id
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot fix discrepancy of type {discrepancy.discrepancy_type}",
            )

        payload = CommonResponse(
            message="Discrepancy fixed successfully",
            success=True,
            payload={"discrepancy_id": str(discrepancy_id), "result": result},
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
