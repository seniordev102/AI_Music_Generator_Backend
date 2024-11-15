import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.credit_management.monthly_allocation.discrepancy_service import (
    DiscrepancyDetectionService,
)
from app.api.credit_management.monthly_allocation.retry_service import (
    AllocationRetryService,
)
from app.api.credit_management.monthly_allocation.service import (
    MonthlyCreditAllocationService,
)
from app.database import db_session
from app.models import UserSubscription

logger = logging.getLogger("app")


class MonthlyAllocationScheduler:
    """Scheduler for coordinating monthly credit allocations and related tasks."""

    def __init__(self, session: AsyncSession, auto_fix_enabled: bool = False):
        self.session = session
        self.auto_fix_enabled = auto_fix_enabled
        self.allocation_service = MonthlyCreditAllocationService(
            session, auto_fix_enabled
        )
        self.retry_service = AllocationRetryService(session)
        self.discrepancy_service = DiscrepancyDetectionService(
            session, auto_fix_enabled
        )

    async def run_monthly_allocations(self) -> Dict:
        """
        Run the monthly allocation process, including:
        1. Allocate credits for eligible subscriptions
        2. Retry failed allocations
        3. Detect and fix discrepancies

        Returns:
            Dict with results from each step
        """
        logger.info("Starting monthly allocation process")
        start_time = datetime.now(timezone.utc)

        # Step 1: Allocate credits for eligible subscriptions
        allocation_results = (
            await self.allocation_service.allocate_credits_for_eligible_subscriptions()
        )

        # Step 2: Retry failed allocations
        retry_results = await self.retry_service.retry_failed_allocations()

        # Step 3: Detect and fix discrepancies
        discrepancy_results = await self.discrepancy_service.detect_discrepancies()

        end_time = datetime.now(timezone.utc)
        duration_seconds = (end_time - start_time).total_seconds()

        # Summarize results
        successful_allocations = sum(
            1 for r in allocation_results if r["status"] == "success"
        )
        skipped_allocations = sum(
            1 for r in allocation_results if r["status"] == "skipped"
        )
        failed_allocations = sum(
            1 for r in allocation_results if r["status"] == "failed"
        )

        successful_retries = sum(1 for r in retry_results if r["status"] == "success")
        scheduled_retries = sum(
            1 for r in retry_results if r["status"] == "retry_scheduled"
        )
        failed_retries = sum(
            1 for r in retry_results if r["status"] in ["retry_error", "failed"]
        )

        fixed_discrepancies = sum(
            1 for r in discrepancy_results if r["status"] == "fixed"
        )
        detected_discrepancies = len(discrepancy_results)

        logger.info(
            f"Monthly allocation process completed in {duration_seconds:.2f} seconds. "
            f"Allocations: {successful_allocations} successful, {skipped_allocations} skipped, {failed_allocations} failed. "
            f"Retries: {successful_retries} successful, {scheduled_retries} scheduled, {failed_retries} failed. "
            f"Discrepancies: {detected_discrepancies} detected, {fixed_discrepancies} fixed."
        )

        return {
            "start_time": start_time,
            "end_time": end_time,
            "duration_seconds": duration_seconds,
            "allocations": {
                "total": len(allocation_results),
                "successful": successful_allocations,
                "skipped": skipped_allocations,
                "failed": failed_allocations,
                "results": allocation_results,
            },
            "retries": {
                "total": len(retry_results),
                "successful": successful_retries,
                "scheduled": scheduled_retries,
                "failed": failed_retries,
                "results": retry_results,
            },
            "discrepancies": {
                "total": detected_discrepancies,
                "fixed": fixed_discrepancies,
                "results": discrepancy_results,
            },
        }

    async def update_next_allocation_dates(self) -> int:
        """
        Update next_credit_allocation_date for all active yearly subscriptions with monthly allocation.
        This should be run after allocations to ensure dates are properly set.

        Returns:
            Number of subscriptions updated
        """
        # Use the session passed to the class
        session = self.session

        # Find all active yearly subscriptions with monthly allocation
        query = select(UserSubscription).where(
            and_(
                UserSubscription.status == "active",
                UserSubscription.billing_cycle == "yearly",
                UserSubscription.credit_allocation_cycle == "monthly",
            )
        )

        result = await session.execute(query)
        subscriptions = result.scalars().all()

        logger.info(
            f"Updating next allocation dates for {len(subscriptions)} subscriptions"
        )

        now = datetime.now(timezone.utc)
        count = 0

        for subscription in subscriptions:
            # Determine the reference date (last allocation date or subscription start date)
            reference_date = subscription.last_credit_allocation_date
            if reference_date is None:
                reference_date = subscription.current_period_start

            if reference_date is None:
                logger.warning(
                    f"Subscription {subscription.id} has no reference date for calculating next allocation"
                )
                continue

            # Calculate the next month's date (same day of month)
            next_month = reference_date.month + 1 if reference_date.month < 12 else 1
            next_year = (
                reference_date.year
                if reference_date.month < 12
                else reference_date.year + 1
            )

            # Handle edge cases for months with different numbers of days
            day = reference_date.day
            # Check if the day exists in the next month
            if day > 28:
                # For months with fewer days, use the last day of that month
                if next_month == 2:  # February
                    # Check for leap year
                    if (next_year % 4 == 0 and next_year % 100 != 0) or (
                        next_year % 400 == 0
                    ):
                        day = min(day, 29)  # Leap year February has 29 days
                    else:
                        day = min(day, 28)  # Non-leap year February has 28 days
                elif next_month in [4, 6, 9, 11]:  # April, June, September, November
                    day = min(day, 30)  # These months have 30 days

            next_allocation = datetime(
                next_year,
                next_month,
                day,
                reference_date.hour,
                reference_date.minute,
                reference_date.second,
                tzinfo=timezone.utc,
            )

            # If the calculated next allocation date is in the past, move it forward
            if next_allocation < now:
                # Move to the month after next
                if next_month == 12:
                    next_month = 1
                    next_year += 1
                else:
                    next_month += 1

                # Handle edge cases again
                if day > 28:
                    if next_month == 2:  # February
                        if (next_year % 4 == 0 and next_year % 100 != 0) or (
                            next_year % 400 == 0
                        ):
                            day = min(day, 29)
                        else:
                            day = min(day, 28)
                    elif next_month in [4, 6, 9, 11]:
                        day = min(day, 30)

                next_allocation = datetime(
                    next_year,
                    next_month,
                    day,
                    reference_date.hour,
                    reference_date.minute,
                    reference_date.second,
                    tzinfo=timezone.utc,
                )

            # Update subscription
            subscription.next_credit_allocation_date = next_allocation
            session.add(subscription)
            count += 1

            logger.info(
                f"Updated subscription {subscription.id} next allocation date to {next_allocation} based on reference date {reference_date}"
            )

        await session.commit()
        logger.info(f"Updated next allocation dates for {count} subscriptions")

        return count


async def run_monthly_allocations(auto_fix_discrepancies: bool = False) -> Dict:
    """
    Run monthly allocations with a new session.

    This is a convenience function for running allocations without having to
    create a session manually.

    Args:
        auto_fix_discrepancies: Whether to automatically fix discrepancies

    Returns:
        Dict with results from the allocation process
    """
    async with db_session() as session:
        scheduler = MonthlyAllocationScheduler(
            session, auto_fix_enabled=auto_fix_discrepancies
        )
        results = await scheduler.run_monthly_allocations()

        # Update next allocation dates
        updated_next_dates = await scheduler.update_next_allocation_dates()
        results["updated_next_dates"] = updated_next_dates

        return results


if __name__ == "__main__":
    # This allows running the allocations directly with: python -m app.api.credit_management.monthly_allocation.scheduler
    logging.basicConfig(level=logging.INFO)

    # Run allocations
    loop = asyncio.get_event_loop()
    results = loop.run_until_complete(
        run_monthly_allocations(auto_fix_discrepancies=False)
    )

    # Print summary
    print("\n=== Monthly Allocation Summary ===")
    print(
        f"Allocations: {results['allocations']['successful']} successful, {results['allocations']['failed']} failed, {results['allocations']['skipped']} skipped"
    )
    print(
        f"Retries: {results['retries']['successful']} successful, {results['retries']['scheduled']} scheduled, {results['retries']['failed']} failed"
    )
    print(
        f"Discrepancies: {results['discrepancies']['total']} detected ({results['discrepancies']['fixed']} fixed)"
    )
    print(
        f"Updated next allocation dates for {results['updated_next_dates']} subscriptions"
    )
    print("===================================")
