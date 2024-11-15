import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.credit_management.monthly_allocation.service import (
    MonthlyCreditAllocationService,
)
from app.models import FailedAllocation, UserSubscription

logger = logging.getLogger("app")


class AllocationRetryService:
    """Service for retrying failed credit allocations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.allocation_service = MonthlyCreditAllocationService(session)
        self.max_retries = 5  # Maximum number of retry attempts

    async def retry_failed_allocations(self) -> List[Dict]:
        """
        Find and retry all failed allocations that are due for retry.

        Returns:
            List of retry results
        """
        now = datetime.now(timezone.utc)

        # Find failed allocations due for retry
        query = select(FailedAllocation).where(
            and_(
                FailedAllocation.status == "pending_retry",
                FailedAllocation.next_retry_at <= now,
                FailedAllocation.retry_count < self.max_retries,
            )
        )

        result = await self.session.execute(query)
        failed_allocations = result.scalars().all()

        logger.info(f"Found {len(failed_allocations)} failed allocations due for retry")

        # Retry each failed allocation
        retry_results = []
        for failed_allocation in failed_allocations:
            try:
                # Get the subscription
                subscription_query = select(UserSubscription).where(
                    UserSubscription.id == failed_allocation.subscription_id
                )
                subscription_result = await self.session.execute(subscription_query)
                subscription = subscription_result.scalar_one_or_none()

                if not subscription:
                    logger.error(
                        f"Subscription {failed_allocation.subscription_id} not found for retry"
                    )
                    await self._mark_retry_failed(
                        failed_allocation, "Subscription not found"
                    )
                    retry_results.append(
                        {
                            "status": "failed",
                            "reason": "subscription_not_found",
                            "failed_allocation_id": failed_allocation.id,
                        }
                    )
                    continue

                # Attempt allocation
                allocation_result = (
                    await self.allocation_service.allocate_monthly_credits(subscription)
                )

                if allocation_result["status"] == "success":
                    # Mark as resolved
                    await self._mark_retry_succeeded(
                        failed_allocation, allocation_result
                    )
                    retry_results.append(
                        {
                            "status": "success",
                            "failed_allocation_id": failed_allocation.id,
                            "allocation_result": allocation_result,
                        }
                    )
                else:
                    # Update retry count and next retry time
                    await self._schedule_next_retry(
                        failed_allocation, allocation_result["reason"]
                    )
                    retry_results.append(
                        {
                            "status": "retry_scheduled",
                            "reason": allocation_result["reason"],
                            "failed_allocation_id": failed_allocation.id,
                            "next_retry_at": failed_allocation.next_retry_at,
                        }
                    )

            except Exception as e:
                logger.error(
                    f"Error retrying allocation {failed_allocation.id}: {str(e)}"
                )
                await self._schedule_next_retry(failed_allocation, str(e))
                retry_results.append(
                    {
                        "status": "retry_error",
                        "reason": str(e),
                        "failed_allocation_id": failed_allocation.id,
                    }
                )

        return retry_results

    async def _mark_retry_succeeded(
        self, failed_allocation: FailedAllocation, allocation_result: Dict
    ) -> None:
        """Mark a failed allocation as successfully retried."""
        failed_allocation.status = "resolved"
        failed_allocation.resolution_notes = f"Successfully allocated on retry. Transaction ID: {allocation_result['transaction_id']}"
        failed_allocation.resolved_at = datetime.now(timezone.utc)

        self.session.add(failed_allocation)
        await self.session.commit()

        logger.info(f"Marked failed allocation {failed_allocation.id} as resolved")

    async def _mark_retry_failed(
        self, failed_allocation: FailedAllocation, reason: str
    ) -> None:
        """Mark a failed allocation as permanently failed."""
        failed_allocation.status = "failed"
        failed_allocation.resolution_notes = f"Permanently failed: {reason}"
        failed_allocation.resolved_at = datetime.now(timezone.utc)

        self.session.add(failed_allocation)
        await self.session.commit()

        logger.info(
            f"Marked failed allocation {failed_allocation.id} as permanently failed"
        )

    async def _schedule_next_retry(
        self, failed_allocation: FailedAllocation, error_message: str
    ) -> None:
        """Schedule the next retry attempt with exponential backoff."""
        failed_allocation.retry_count += 1
        failed_allocation.error_message = error_message

        # Calculate next retry time with exponential backoff
        # 1 hour, 2 hours, 4 hours, 8 hours, 16 hours
        hours_delay = 2 ** (failed_allocation.retry_count - 1)
        failed_allocation.next_retry_at = datetime.now(timezone.utc) + timedelta(
            hours=hours_delay
        )

        # If max retries reached, mark as failed
        if failed_allocation.retry_count >= self.max_retries:
            failed_allocation.status = "failed"
            failed_allocation.resolution_notes = (
                f"Max retries ({self.max_retries}) reached"
            )
            failed_allocation.resolved_at = datetime.now(timezone.utc)

        self.session.add(failed_allocation)
        await self.session.commit()

        logger.info(
            f"Scheduled retry #{failed_allocation.retry_count} for allocation {failed_allocation.id} "
            f"at {failed_allocation.next_retry_at}"
        )
