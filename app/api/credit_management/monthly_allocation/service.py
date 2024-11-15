import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AllocationDiscrepancy,
    CreditAllocationHistory,
    CreditPackage,
    CreditTransaction,
    FailedAllocation,
    TransactionSource,
    TransactionType,
    User,
    UserCreditBalance,
    UserSubscription,
)

logger = logging.getLogger("app")


class MonthlyCreditAllocationService:
    """Service for handling monthly credit allocations for yearly subscriptions."""

    def __init__(self, session: AsyncSession, auto_fix_enabled: bool = False):
        self.session = session
        self.auto_fix_enabled = auto_fix_enabled

    async def allocate_credits_for_eligible_subscriptions(self) -> List[Dict]:
        """
        Find all eligible subscriptions and allocate monthly credits.

        Eligible subscriptions are:
        - Active
        - Yearly billing cycle
        - Monthly credit allocation cycle
        - Due for allocation (no allocation this month)

        Returns:
            List of allocation results
        """
        now = datetime.now(timezone.utc)
        current_month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

        # Find eligible subscriptions
        query = select(UserSubscription).where(
            and_(
                UserSubscription.status == "active",
                UserSubscription.billing_cycle == "yearly",
                UserSubscription.credit_allocation_cycle == "monthly",
                # Either no allocation date or last allocation was before this month
                (
                    UserSubscription.last_credit_allocation_date.is_(None)
                    | (
                        (
                            UserSubscription.last_credit_allocation_date
                            < current_month_start
                        )
                    )
                ),
            )
        )

        result = await self.session.execute(query)
        eligible_subscriptions = result.scalars().all()

        logger.info(
            f"Found {len(eligible_subscriptions)} eligible subscriptions for credit allocation"
        )

        # Allocate credits for each eligible subscription
        allocation_results = []
        for subscription in eligible_subscriptions:
            try:
                result = await self.allocate_monthly_credits(subscription)
                allocation_results.append(result)
            except Exception as e:
                logger.error(
                    f"Error allocating credits for subscription {subscription.id}: {str(e)}"
                )
                # Record failed allocation
                await self._record_failed_allocation(
                    subscription, f"Error in batch allocation: {str(e)}"
                )
                allocation_results.append(
                    {
                        "status": "failed",
                        "reason": str(e),
                        "subscription_id": subscription.id,
                    }
                )

        return allocation_results

    async def allocate_monthly_credits(self, subscription: UserSubscription) -> Dict:
        """
        Allocate monthly credits for a yearly subscription.

        Args:
            subscription: The subscription to allocate credits for

        Returns:
            Dict with status and details
        """
        try:
            # Check if already allocated this month
            now = datetime.now(timezone.utc)
            current_month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

            if (
                subscription.last_credit_allocation_date
                and subscription.last_credit_allocation_date.year == now.year
                and subscription.last_credit_allocation_date.month == now.month
            ):
                return {
                    "status": "skipped",
                    "reason": "already_allocated_this_month",
                    "subscription_id": subscription.id,
                }

            # Check if this is the first month of the subscription and the user already received initial credits
            subscription_start_month = subscription.current_period_start.month
            subscription_start_year = subscription.current_period_start.year

            if (
                now.month == subscription_start_month
                and now.year == subscription_start_year
            ):
                # For the first month, we'll skip the check for existing transactions
                # and assume the initial credits were already allocated when the subscription was created
                logger.info(
                    f"Skipping allocation for subscription {subscription.id} as it's in the first month"
                )
                return {
                    "status": "skipped",
                    "reason": "first_month_of_subscription",
                    "subscription_id": subscription.id,
                }

            # Get package details
            try:
                package = await self._get_package_details_by_id(subscription.package_id)
            except Exception as e:
                error_msg = f"Package not found: {str(e)}"
                await self._record_failed_allocation(subscription, error_msg)
                return {
                    "status": "failed",
                    "reason": error_msg,
                    "subscription_id": subscription.id,
                }

            # Use the full package credits amount (no division by 12)
            # For yearly subscriptions, the package credits are already defined as monthly
            monthly_credits = package.credits

            # Create transaction
            transaction_id = uuid4()
            transaction = CreditTransaction(
                id=transaction_id,
                user_id=subscription.user_id,
                transaction_type="credit",
                transaction_source="subscription_renewal",
                amount=monthly_credits,
                balance_after=monthly_credits,  # Will be updated later
                description="Monthly credit allocation for yearly subscription",
                subscription_id=subscription.id,
                package_id=subscription.package_id,
                credit_metadata={
                    "allocation_type": "monthly",
                    "billing_cycle": subscription.billing_cycle,
                    "allocation_month": f"{now.year}-{now.month:02d}",
                },
            )

            # Create balance
            balance_id = uuid4()
            balance = UserCreditBalance(
                id=balance_id,
                user_id=subscription.user_id,
                package_id=subscription.package_id,
                transaction_id=transaction_id,
                initial_amount=monthly_credits,
                remaining_amount=monthly_credits,
                expires_at=None,  # Monthly allocations don't expire
                is_active=True,
            )

            # First save the transaction and balance to ensure they exist in the database
            self.session.add(transaction)
            self.session.add(balance)

            try:
                # Commit the transaction and balance first to ensure they exist
                await self.session.commit()
                logger.info(
                    f"Created transaction {transaction_id} and balance {balance_id}"
                )
            except Exception as e:
                await self.session.rollback()
                error_msg = f"Error creating transaction and balance: {str(e)}"
                logger.error(error_msg)
                await self._record_failed_allocation(subscription, error_msg)
                return {
                    "status": "failed",
                    "reason": error_msg,
                    "subscription_id": subscription.id,
                }

            # Now create the allocation history record
            allocation_id = uuid4()
            history = CreditAllocationHistory(
                id=allocation_id,
                subscription_id=subscription.id,
                transaction_id=transaction_id,
                balance_id=balance_id,
                allocation_id=str(allocation_id),
                user_id=subscription.user_id,
                credits_allocated=monthly_credits,
                allocation_period=f"{now.year}-{now.month:02d}",
                status="success",
            )

            # Update subscription
            subscription.last_credit_allocation_date = now

            # Save the history record and update the subscription
            self.session.add(history)
            self.session.add(subscription)

            try:
                await self.session.commit()
                logger.info(
                    f"Created allocation history {allocation_id} and updated subscription"
                )
            except Exception as e:
                await self.session.rollback()
                error_msg = f"Error creating allocation history: {str(e)}"
                logger.error(error_msg)
                # We don't need to record a failed allocation here since the credits were already allocated
                return {
                    "status": "partial_success",
                    "reason": f"Credits allocated but failed to record history: {error_msg}",
                    "subscription_id": subscription.id,
                    "transaction_id": transaction_id,
                    "balance_id": balance_id,
                }

            logger.info(
                f"Allocated {monthly_credits} monthly credits for subscription {subscription.id}"
            )

            return {
                "status": "success",
                "transaction_id": transaction_id,
                "balance_id": balance_id,
                "amount": monthly_credits,
                "subscription_id": subscription.id,
            }

        except Exception as e:
            await self.session.rollback()
            error_msg = f"Error allocating monthly credits: {str(e)}"
            logger.error(error_msg)

            # Record failed allocation
            await self._record_failed_allocation(subscription, error_msg)

            return {
                "status": "failed",
                "reason": error_msg,
                "subscription_id": subscription.id,
            }

    async def _get_package_details_by_id(self, package_id: str) -> CreditPackage:
        """Get package details by ID."""
        query = select(CreditPackage).where(CreditPackage.id == package_id)
        result = await self.session.execute(query)
        package = result.scalar_one_or_none()

        if not package:
            raise ValueError(f"Package with ID {package_id} not found")

        return package

    async def _get_or_create_balance(self, email: str) -> Dict:
        """Get or create user balance."""
        # This is a placeholder - implement the actual logic based on your application
        # This should match the implementation in your existing credit management service
        query = select(User).where(User.email == email)
        result = await self.session.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail=f"User not found: {email}")

        # Get active balances
        active_balances_query = select(UserCreditBalance).where(
            and_(
                UserCreditBalance.user_id == user.id,
                UserCreditBalance.is_active == True,
                UserCreditBalance.remaining_amount > 0,
                or_(
                    UserCreditBalance.expires_at > datetime.now(timezone.utc),
                    UserCreditBalance.expires_at == None,
                ),
            )
        )

        active_balances_result = await self.session.execute(active_balances_query)
        active_balances = active_balances_result.scalars().all()

        # Calculate total available credits
        current_balance = sum(balance.remaining_amount for balance in active_balances)

        return {"current_balance": current_balance, "user_id": user.id}

    async def _create_monthly_allocation_transaction(
        self,
        subscription: UserSubscription,
        monthly_credits: int,
        new_balance: int,
        allocation_id: str,
    ) -> CreditTransaction:
        """Create a transaction for monthly credit allocation."""
        transaction = CreditTransaction(
            user_id=subscription.user_id,
            transaction_type=TransactionType.CREDIT,
            transaction_source=TransactionSource.SUBSCRIPTION_RENEWAL,
            amount=monthly_credits,
            balance_after=new_balance,
            description="Monthly credit allocation for yearly subscription",
            subscription_id=subscription.id,
            package_id=subscription.package_id,
            credit_metadata={
                "allocation_id": allocation_id,
                "allocation_type": "monthly",
                "billing_cycle": "yearly",
                "period": datetime.now(timezone.utc).strftime("%Y-%m"),
            },
        )
        self.session.add(transaction)
        await self.session.flush()
        logger.info(f"Created monthly allocation transaction with ID: {transaction.id}")
        return transaction

    async def _create_monthly_allocation_balance(
        self,
        subscription: UserSubscription,
        transaction: CreditTransaction,
        monthly_credits: int,
    ) -> UserCreditBalance:
        """Create a balance record for monthly credit allocation."""
        # Calculate expiration date
        package = await self._get_package_details_by_id(str(subscription.package_id))
        current_time = datetime.now(timezone.utc)
        expiration_date = None
        if package.expiration_days:
            expiration_date = current_time + timedelta(days=package.expiration_days)

        # Create balance record
        balance = UserCreditBalance(
            user_id=subscription.user_id,
            package_id=subscription.package_id,
            transaction_id=transaction.id,
            initial_amount=monthly_credits,
            remaining_amount=monthly_credits,
            expires_at=expiration_date,
            is_active=True,
        )
        self.session.add(balance)
        await self.session.flush()
        logger.info(f"Created monthly allocation balance with ID: {balance.id}")
        return balance

    async def _calculate_next_allocation_date(
        self, subscription: UserSubscription
    ) -> datetime:
        """Calculate the next allocation date based on the subscription cycle."""
        now = datetime.now(timezone.utc)

        # For monthly allocations, set to the 1st of next month
        next_month = now.month + 1 if now.month < 12 else 1
        next_year = now.year if now.month < 12 else now.year + 1

        return datetime(next_year, next_month, 1, tzinfo=timezone.utc)

    async def _is_already_allocated(self, allocation_id: str) -> bool:
        """Check if credits have already been allocated for this period."""
        query = select(CreditAllocationHistory).where(
            CreditAllocationHistory.allocation_id == allocation_id
        )
        result = await self.session.execute(query)
        existing_allocation = result.scalar_one_or_none()

        return existing_allocation is not None

    async def _record_allocation_history(
        self,
        subscription: UserSubscription,
        transaction: CreditTransaction,
        balance: UserCreditBalance,
        allocation_id: str,
        credits_allocated: int,
    ) -> None:
        """Record allocation history for auditing and idempotency."""
        history = CreditAllocationHistory(
            subscription_id=subscription.id,
            user_id=subscription.user_id,
            transaction_id=transaction.id,
            balance_id=balance.id,
            allocation_id=allocation_id,
            credits_allocated=credits_allocated,
            allocation_period=datetime.now(timezone.utc).strftime("%Y-%m"),
            status="completed",
        )
        self.session.add(history)
        await self.session.flush()
        logger.info(f"Recorded allocation history with ID: {history.id}")

    async def _record_failed_allocation(
        self, subscription: UserSubscription, error_message: str
    ) -> FailedAllocation:
        """Record a failed allocation attempt."""
        failed_allocation = FailedAllocation(
            id=uuid4(),
            subscription_id=subscription.id,
            user_id=subscription.user_id,
            error_message=error_message,
            retry_count=0,
            status="pending_retry",
            next_retry_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        self.session.add(failed_allocation)
        await self.session.commit()

        logger.info(
            f"Recorded failed allocation for subscription {subscription.id}: {error_message}"
        )

        return failed_allocation

    def _calculate_next_retry_time(self, retry_count: int) -> datetime:
        """Calculate next retry time with exponential backoff."""
        # Exponential backoff: 1h, 2h, 4h, 8h, 16h
        hours = 2**retry_count if retry_count < 5 else 24
        return datetime.now(timezone.utc) + timedelta(hours=hours)

    async def _get_eligible_subscriptions(self) -> List[UserSubscription]:
        """
        Get all subscriptions eligible for monthly credit allocation.

        Eligible subscriptions are:
        - Active
        - Yearly billing cycle
        - Monthly credit allocation cycle

        Returns:
            List of eligible subscriptions
        """
        now = datetime.now(timezone.utc)
        current_month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

        # Find eligible subscriptions
        query = select(UserSubscription).where(
            and_(
                UserSubscription.status == "active",
                UserSubscription.billing_cycle == "yearly",
                UserSubscription.credit_allocation_cycle == "monthly",
            )
        )

        result = await self.session.execute(query)
        return result.scalars().all()
