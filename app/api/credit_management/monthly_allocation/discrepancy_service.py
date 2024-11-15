import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AllocationDiscrepancy,
    CreditAllocationHistory,
    CreditPackage,
    CreditTransaction,
    UserCreditBalance,
    UserSubscription,
)

logger = logging.getLogger("app")


class DiscrepancyDetectionService:
    """Service for detecting and fixing discrepancies in credit allocations."""

    def __init__(self, session: AsyncSession, auto_fix_enabled: bool = False):
        self.session = session
        self.auto_fix_enabled = auto_fix_enabled
        self.months_to_check = 3  # Check the last 3 months by default

    async def detect_discrepancies(self) -> List[Dict]:
        """
        Detect discrepancies in credit allocations for yearly subscriptions.

        Checks:
        1. Missing allocations - months where credits should have been allocated but weren't
        2. Incorrect amounts - allocations with incorrect credit amounts

        Returns:
            List of detected discrepancies
        """
        # Find active yearly subscriptions with monthly allocation
        query = select(UserSubscription).where(
            and_(
                UserSubscription.status == "active",
                UserSubscription.billing_cycle == "yearly",
                UserSubscription.credit_allocation_cycle == "monthly",
            )
        )

        result = await self.session.execute(query)
        subscriptions = result.scalars().all()

        logger.info(
            f"Checking {len(subscriptions)} subscriptions for allocation discrepancies"
        )

        discrepancies = []
        for subscription in subscriptions:
            try:
                # Get expected allocations
                expected_allocations = await self._get_expected_allocations(
                    subscription, self.months_to_check
                )

                # Get actual allocations
                actual_allocations = await self._get_actual_allocations(
                    subscription, self.months_to_check
                )

                # Compare and find discrepancies
                subscription_discrepancies = self._compare_allocations(
                    subscription, expected_allocations, actual_allocations
                )

                if subscription_discrepancies:
                    # Record discrepancies
                    for discrepancy in subscription_discrepancies:
                        recorded_discrepancy = await self._record_discrepancy(
                            subscription, discrepancy
                        )
                        discrepancies.append(recorded_discrepancy)

                        # Auto-fix if enabled
                        if (
                            self.auto_fix_enabled
                            and discrepancy["type"] == "missing_allocation"
                        ):
                            await self._fix_missing_allocation(
                                subscription, discrepancy, recorded_discrepancy["id"]
                            )

            except Exception as e:
                logger.error(
                    f"Error detecting discrepancies for subscription {subscription.id}: {str(e)}"
                )

        return discrepancies

    async def _get_expected_allocations(
        self, subscription: UserSubscription, months_to_check: int
    ) -> List[Dict]:
        """
        Calculate expected allocations for a subscription over the past N months.

        Args:
            subscription: The subscription to check
            months_to_check: Number of months to look back

        Returns:
            List of expected allocations with month and amount
        """
        # Get package details
        query = select(CreditPackage).where(CreditPackage.id == subscription.package_id)
        result = await self.session.execute(query)
        package = result.scalar_one_or_none()

        if not package:
            logger.error(f"Package not found for subscription {subscription.id}")
            return []

        # Calculate monthly credit amount
        monthly_credits = package.credits // 12

        # Calculate expected allocations for past months
        now = datetime.now(timezone.utc)
        expected_allocations = []

        for i in range(months_to_check):
            # Calculate month (going backwards from current month)
            month = now.month - i
            year = now.year

            # Handle year boundary
            if month <= 0:
                month += 12
                year -= 1

            # Check if subscription was active in this month
            subscription_start = subscription.current_period_start
            if subscription_start and (
                year < subscription_start.year
                or (
                    year == subscription_start.year and month < subscription_start.month
                )
            ):
                # Subscription wasn't active yet
                continue

            # Add expected allocation
            expected_allocations.append(
                {"period": f"{year}-{month:02d}", "expected_amount": monthly_credits}
            )

        return expected_allocations

    async def _get_actual_allocations(
        self, subscription: UserSubscription, months_to_check: int
    ) -> List[Dict]:
        """
        Get actual allocations for a subscription over the past N months.

        Args:
            subscription: The subscription to check
            months_to_check: Number of months to look back

        Returns:
            List of actual allocations with month and amount
        """
        now = datetime.now(timezone.utc)
        start_date = datetime(
            now.year - (1 if now.month <= months_to_check else 0),
            (now.month - months_to_check) % 12
            + (12 if now.month <= months_to_check else 0),
            1,
            tzinfo=timezone.utc,
        )

        # Query allocation history
        query = select(CreditAllocationHistory).where(
            and_(
                CreditAllocationHistory.subscription_id == subscription.id,
                CreditAllocationHistory.status == "success",
                CreditAllocationHistory.created_at >= start_date,
            )
        )

        result = await self.session.execute(query)
        allocations = result.scalars().all()

        # Group by period
        actual_allocations = {}
        for allocation in allocations:
            period = allocation.allocation_period
            if period in actual_allocations:
                actual_allocations[period] += allocation.credits_allocated
            else:
                actual_allocations[period] = allocation.credits_allocated

        return [
            {"period": period, "actual_amount": amount}
            for period, amount in actual_allocations.items()
        ]

    def _compare_allocations(
        self,
        subscription: UserSubscription,
        expected_allocations: List[Dict],
        actual_allocations: List[Dict],
    ) -> List[Dict]:
        """
        Compare expected and actual allocations to find discrepancies.

        Args:
            subscription: The subscription being checked
            expected_allocations: List of expected allocations
            actual_allocations: List of actual allocations

        Returns:
            List of discrepancies
        """
        discrepancies = []

        # Convert actual allocations to dict for easier lookup
        actual_by_period = {a["period"]: a["actual_amount"] for a in actual_allocations}

        # Check each expected allocation
        for expected in expected_allocations:
            period = expected["period"]
            expected_amount = expected["expected_amount"]

            if period not in actual_by_period:
                # Missing allocation
                discrepancies.append(
                    {
                        "type": "missing_allocation",
                        "period": period,
                        "expected_amount": expected_amount,
                        "actual_amount": 0,
                    }
                )
            elif actual_by_period[period] != expected_amount:
                # Incorrect amount
                discrepancies.append(
                    {
                        "type": "incorrect_amount",
                        "period": period,
                        "expected_amount": expected_amount,
                        "actual_amount": actual_by_period[period],
                    }
                )

        return discrepancies

    async def _record_discrepancy(
        self, subscription: UserSubscription, discrepancy: Dict
    ) -> Dict:
        """
        Record a detected discrepancy.

        Args:
            subscription: The subscription with the discrepancy
            discrepancy: The discrepancy details

        Returns:
            Dict with recorded discrepancy details
        """
        discrepancy_record = AllocationDiscrepancy(
            id=uuid4(),
            subscription_id=subscription.id,
            user_id=subscription.user_id,
            discrepancy_type=discrepancy["type"],
            allocation_period=discrepancy["period"],
            expected_amount=discrepancy["expected_amount"],
            actual_amount=discrepancy["actual_amount"],
            status="detected",
        )

        self.session.add(discrepancy_record)
        await self.session.commit()

        logger.info(
            f"Recorded {discrepancy['type']} discrepancy for subscription {subscription.id} "
            f"in period {discrepancy['period']}"
        )

        return {
            "id": discrepancy_record.id,
            "subscription_id": subscription.id,
            "type": discrepancy["type"],
            "period": discrepancy["period"],
            "expected_amount": discrepancy["expected_amount"],
            "actual_amount": discrepancy["actual_amount"],
            "status": "detected",
        }

    async def _fix_missing_allocation(
        self, subscription: UserSubscription, discrepancy: Dict, discrepancy_id: UUID
    ) -> Dict:
        """
        Fix a missing allocation by creating the necessary records.

        Args:
            subscription: The subscription to fix
            discrepancy: The discrepancy details
            discrepancy_id: The ID of the recorded discrepancy

        Returns:
            Dict with fix result
        """
        try:
            period = discrepancy["period"]
            amount = discrepancy["expected_amount"]

            # Create transaction
            transaction_id = uuid4()
            transaction = CreditTransaction(
                id=transaction_id,
                user_id=subscription.user_id,
                transaction_type="credit",
                transaction_source="discrepancy_fix",
                amount=amount,
                balance_after=amount,  # Will be updated later
                description=f"Discrepancy fix: Missing allocation for {period}",
                subscription_id=subscription.id,
                package_id=subscription.package_id,
                credit_metadata={
                    "allocation_type": "discrepancy_fix",
                    "allocation_period": period,
                    "discrepancy_id": str(discrepancy_id),
                },
            )

            # Create balance
            balance_id = uuid4()
            balance = UserCreditBalance(
                id=balance_id,
                user_id=subscription.user_id,
                package_id=subscription.package_id,
                transaction_id=transaction_id,
                initial_amount=amount,
                remaining_amount=amount,
                expires_at=None,  # Monthly allocations don't expire
                is_active=True,
            )

            # Create allocation history
            allocation_id = uuid4()
            history = CreditAllocationHistory(
                id=allocation_id,
                subscription_id=subscription.id,
                transaction_id=transaction_id,
                balance_id=balance_id,
                allocation_id=str(allocation_id),
                user_id=subscription.user_id,
                credits_allocated=amount,
                allocation_period=period,
                status="success",
                allocation_type="discrepancy_fix",
            )

            # Update discrepancy record
            discrepancy_record = await self.session.get(
                AllocationDiscrepancy, discrepancy_id
            )
            if discrepancy_record:
                discrepancy_record.status = "fixed"
                discrepancy_record.resolution_notes = (
                    f"Auto-fixed. Transaction ID: {transaction_id}"
                )
                discrepancy_record.resolved_at = datetime.now(timezone.utc)
                self.session.add(discrepancy_record)

            # Save everything
            self.session.add(transaction)
            self.session.add(balance)
            self.session.add(history)
            await self.session.commit()

            logger.info(
                f"Fixed missing allocation for subscription {subscription.id} in period {period}"
            )

            return {
                "status": "fixed",
                "discrepancy_id": discrepancy_id,
                "transaction_id": transaction_id,
                "balance_id": balance_id,
                "allocation_id": allocation_id,
            }

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error fixing discrepancy {discrepancy_id}: {str(e)}")

            # Update discrepancy record to show fix failed
            try:
                discrepancy_record = await self.session.get(
                    AllocationDiscrepancy, discrepancy_id
                )
                if discrepancy_record:
                    discrepancy_record.status = "fix_failed"
                    discrepancy_record.resolution_notes = f"Auto-fix failed: {str(e)}"
                    self.session.add(discrepancy_record)
                    await self.session.commit()
            except Exception as inner_e:
                logger.error(f"Error updating discrepancy record: {str(inner_e)}")

            return {
                "status": "fix_failed",
                "discrepancy_id": discrepancy_id,
                "error": str(e),
            }
