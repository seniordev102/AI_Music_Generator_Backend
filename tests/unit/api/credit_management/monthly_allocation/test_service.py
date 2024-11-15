import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.credit_management.monthly_allocation.service import (
    MonthlyCreditAllocationService,
)
from app.models import (
    CreditAllocationHistory,
    CreditPackage,
    CreditTransaction,
    FailedAllocation,
    UserCreditBalance,
    UserSubscription,
)


@pytest.fixture
def mock_session():
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def yearly_subscription():
    return UserSubscription(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        package_id=uuid.uuid4(),
        status="active",
        billing_cycle="yearly",
        credit_allocation_cycle="monthly",
        current_period_start=datetime.now(timezone.utc) - timedelta(days=30),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=335),
        last_credit_allocation_date=None,
        next_credit_allocation_date=None,
    )


@pytest.fixture
def package():
    return CreditPackage(
        id=uuid.uuid4(),
        name="Yearly Pro",
        credits=12000,  # 1000 credits per month
        subscription_period="yearly",
    )


@pytest.mark.asyncio
async def test_allocate_monthly_credits(mock_session, yearly_subscription, package):
    # Setup
    service = MonthlyCreditAllocationService(mock_session)

    # Mock the package query result
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = package
    mock_session.execute.return_value = mock_result

    # Call the method
    result = await service.allocate_monthly_credits(yearly_subscription)

    # Assertions
    assert result["status"] == "success"
    assert "transaction_id" in result
    assert "balance_id" in result
    assert result["amount"] == 1000  # 12000 / 12 = 1000
    assert (
        mock_session.add.call_count == 4
    )  # Transaction, Balance, History, Subscription
    assert mock_session.commit.call_count == 1


@pytest.mark.asyncio
async def test_allocate_monthly_credits_already_allocated(
    mock_session, yearly_subscription
):
    # Setup - subscription that already had credits allocated this month
    now = datetime.now(timezone.utc)
    yearly_subscription.last_credit_allocation_date = datetime(
        now.year, now.month, 1, tzinfo=timezone.utc
    )

    service = MonthlyCreditAllocationService(mock_session)

    # Call the method
    result = await service.allocate_monthly_credits(yearly_subscription)

    # Assertions
    assert result["status"] == "skipped"
    assert result["reason"] == "already_allocated_this_month"
    assert mock_session.add.call_count == 0
    assert mock_session.commit.call_count == 0


@pytest.mark.asyncio
async def test_allocate_monthly_credits_package_not_found(
    mock_session, yearly_subscription
):
    # Setup
    service = MonthlyCreditAllocationService(mock_session)

    # Mock the package query result - package not found
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    # Call the method
    result = await service.allocate_monthly_credits(yearly_subscription)

    # Assertions
    assert result["status"] == "failed"
    assert "Package with ID" in result["reason"]
    assert mock_session.add.call_count == 1  # FailedAllocation
    assert mock_session.commit.call_count == 1


@pytest.mark.asyncio
async def test_allocate_credits_for_eligible_subscriptions(mock_session):
    # Setup
    service = MonthlyCreditAllocationService(mock_session)

    # Mock the eligible subscriptions query
    sub1 = UserSubscription(id=uuid.uuid4())
    sub2 = UserSubscription(id=uuid.uuid4())
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [sub1, sub2]
    mock_session.execute.return_value = mock_result

    # Mock the allocate_monthly_credits method
    with patch.object(
        service,
        "allocate_monthly_credits",
        new_callable=AsyncMock,
        return_value={"status": "success"},
    ) as mock_allocate:
        # Call the method
        results = await service.allocate_credits_for_eligible_subscriptions()

        # Assertions
        assert len(results) == 2
        assert mock_allocate.call_count == 2
        mock_allocate.assert_any_call(sub1)
        mock_allocate.assert_any_call(sub2)


@pytest.mark.asyncio
async def test_record_failed_allocation(mock_session, yearly_subscription):
    # Setup
    service = MonthlyCreditAllocationService(mock_session)
    error_message = "Test error message"

    # Call the method
    result = await service._record_failed_allocation(yearly_subscription, error_message)

    # Assertions
    assert isinstance(result, FailedAllocation)
    assert result.subscription_id == yearly_subscription.id
    assert result.user_id == yearly_subscription.user_id
    assert result.error_message == error_message
    assert result.retry_count == 0
    assert result.status == "pending_retry"
    assert mock_session.add.call_count == 1
    assert mock_session.commit.call_count == 1
