import asyncio
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
import stripe
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.api.credit_management.stripe.service import StripeCreditManagementService
from app.database import db_session, get_session
from app.models import (
    Base,
    CreditPackage,
    CreditTransaction,
    TransactionSource,
    TransactionType,
    User,
    UserCreditBalance,
    UserSubscription,
)

# Create a test database URL - use SQLite for simplicity in tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create async engine and session
engine = create_async_engine(TEST_DATABASE_URL, echo=True)
TestingSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# Override the dependency
async def override_get_session() -> AsyncSession:
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture(scope="function")
async def setup_database():
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Provide the session
    async with TestingSessionLocal() as session:
        yield session

    # Drop tables after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def user(setup_database):
    """Create a test user in the database."""
    session = setup_database
    user = User(
        email="test@example.com",
        first_name="Test",
        last_name="User",
        password_hash="hashed_password",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture
async def credit_package(setup_database):
    """Create a test credit package in the database."""
    session = setup_database
    package = CreditPackage(
        name="Yearly Subscription",
        credits=9600,  # 800 per month
        price=99.99,
        is_subscription=True,
        expiration_days=365,
        stripe_product_id="prod_test",
        stripe_price_id="price_test",
    )
    session.add(package)
    await session.commit()
    await session.refresh(package)
    return package


@pytest.fixture
async def subscription(setup_database, user, credit_package):
    """Create a test subscription in the database."""
    session = setup_database
    subscription = UserSubscription(
        user_id=user.id,
        package_id=credit_package.id,
        platform="stripe",
        platform_subscription_id="sub_test123",
        status="active",
        current_period_start=datetime.now(timezone.utc) - timedelta(days=30),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=335),
        credits_per_period=9600,  # 800 per month
    )
    session.add(subscription)
    await session.commit()
    await session.refresh(subscription)
    return subscription


@pytest.fixture
async def credit_balance(setup_database, user, credit_package, subscription):
    """Create a test credit balance in the database."""
    session = setup_database

    # First create a transaction
    transaction = CreditTransaction(
        user_id=user.id,
        transaction_type=TransactionType.CREDIT,
        transaction_source=TransactionSource.SUBSCRIPTION_RENEWAL,
        amount=800,
        balance_after=800,
        description="Initial subscription credits",
        subscription_id=subscription.id,
        package_id=credit_package.id,
        credit_metadata={
            "subscription_id": subscription.platform_subscription_id,
        },
    )
    session.add(transaction)
    await session.flush()

    # Then create a balance linked to the transaction
    balance = UserCreditBalance(
        user_id=user.id,
        package_id=credit_package.id,
        transaction_id=transaction.id,
        initial_amount=800,
        remaining_amount=799,  # 1 credit used
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        is_active=True,
    )
    session.add(balance)
    await session.commit()
    await session.refresh(balance)
    return balance


@pytest.fixture
def stripe_service(setup_database):
    """Create a StripeCreditManagementService with the test database session."""
    return StripeCreditManagementService(session=setup_database)


@pytest.mark.asyncio
class TestIntegrationSubscriptionRenewal:
    """Integration tests for subscription renewal functionality."""

    @pytest.mark.asyncio
    async def test_full_renewal_flow(
        self,
        setup_database,
        user,
        credit_package,
        subscription,
        credit_balance,
        stripe_service,
    ):
        """Test the full subscription renewal flow with rollover credits."""
        # Mock Stripe API responses
        mock_stripe_subscription = MagicMock()
        mock_stripe_subscription.id = subscription.platform_subscription_id
        mock_stripe_subscription.current_period_start = int(
            datetime.now(timezone.utc).timestamp()
        )
        mock_stripe_subscription.current_period_end = int(
            (datetime.now(timezone.utc) + timedelta(days=30)).timestamp()
        )

        # Create a mock invoice
        mock_invoice = MagicMock()
        mock_invoice.id = "invoice_test123"
        mock_invoice.subscription = subscription.platform_subscription_id

        # Process the invoice payment
        with patch(
            "stripe.Subscription.retrieve", return_value=mock_stripe_subscription
        ):
            await stripe_service.handle_invoice_payment_succeeded(mock_invoice)

        # Query the database to verify the results
        session = setup_database

        # Check transactions
        transactions_query = select(CreditTransaction).where(
            CreditTransaction.user_id == user.id
        )
        result = await session.execute(transactions_query)
        transactions = result.scalars().all()

        # Should have at least 3 transactions:
        # 1. Original subscription
        # 2. New subscription credits
        # 3. Rollover credits
        assert len(transactions) >= 3

        # Find the rollover transaction
        rollover_transaction = None
        for transaction in transactions:
            if transaction.credit_metadata.get("is_rollover") is True:
                rollover_transaction = transaction
                break

        assert rollover_transaction is not None
        assert (
            rollover_transaction.amount == 799
        )  # The remaining amount from the original balance

        # Check balances
        balances_query = select(UserCreditBalance).where(
            UserCreditBalance.user_id == user.id
        )
        result = await session.execute(balances_query)
        balances = result.scalars().all()

        # Should have at least 3 balances:
        # 1. Original balance (now inactive)
        # 2. New subscription balance
        # 3. Rollover balance
        assert len(balances) >= 3

        # Verify the original balance is now inactive
        original_balance = None
        for balance in balances:
            if balance.id == credit_balance.id:
                original_balance = balance
                break

        assert original_balance is not None
        assert original_balance.is_active is False

        # Verify we have active balances for the new credits and rollover
        active_balances = [b for b in balances if b.is_active is True]
        assert len(active_balances) >= 2

        # Calculate total active credits
        total_active_credits = sum(b.remaining_amount for b in active_balances)

        # Should be 9600 (new subscription) + 799 (rollover) = 10399
        assert total_active_credits == 10399

    @pytest.mark.asyncio
    async def test_monthly_credit_allocation(
        self, setup_database, user, credit_package, subscription, stripe_service
    ):
        """Test the monthly credit allocation for yearly subscriptions."""
        # Process monthly credits
        await stripe_service.process_yearly_subscription_monthly_credits(
            user_email=user.email
        )

        # Query the database to verify the results
        session = setup_database

        # Check transactions
        transactions_query = select(CreditTransaction).where(
            CreditTransaction.user_id == user.id,
            CreditTransaction.credit_metadata.contains({"monthly_allocation": True}),
        )
        result = await session.execute(transactions_query)
        transactions = result.scalars().all()

        # Should have at least 1 transaction for monthly allocation
        assert len(transactions) >= 1

        # Verify the transaction amount (yearly credits / 12)
        monthly_transaction = transactions[0]
        assert monthly_transaction.amount == subscription.credits_per_period / 12

        # Check balances
        balances_query = select(UserCreditBalance).where(
            UserCreditBalance.user_id == user.id, UserCreditBalance.is_active == True
        )
        result = await session.execute(balances_query)
        balances = result.scalars().all()

        # Should have at least 1 active balance
        assert len(balances) >= 1

        # Calculate total active credits
        total_active_credits = sum(b.remaining_amount for b in balances)

        # Should be subscription.credits_per_period / 12 = 800
        assert total_active_credits == 800

    @pytest.mark.asyncio
    async def test_expired_credits_not_rolled_over_integration(
        self, setup_database, user, credit_package, subscription, stripe_service
    ):
        """Test that expired credits are not included in rollover in a real database."""
        session = setup_database

        # Create an expired balance
        expired_transaction = CreditTransaction(
            user_id=user.id,
            transaction_type=TransactionType.CREDIT,
            transaction_source=TransactionSource.SUBSCRIPTION_RENEWAL,
            amount=500,
            balance_after=500,
            description="Expired credits",
            subscription_id=subscription.id,
            package_id=credit_package.id,
        )
        session.add(expired_transaction)
        await session.flush()

        expired_balance = UserCreditBalance(
            user_id=user.id,
            package_id=credit_package.id,
            transaction_id=expired_transaction.id,
            initial_amount=500,
            remaining_amount=500,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),  # Expired
            is_active=True,
        )
        session.add(expired_balance)

        # Create a valid balance
        valid_transaction = CreditTransaction(
            user_id=user.id,
            transaction_type=TransactionType.CREDIT,
            transaction_source=TransactionSource.SUBSCRIPTION_RENEWAL,
            amount=300,
            balance_after=800,  # 500 + 300
            description="Valid credits",
            subscription_id=subscription.id,
            package_id=credit_package.id,
        )
        session.add(valid_transaction)
        await session.flush()

        valid_balance = UserCreditBalance(
            user_id=user.id,
            package_id=credit_package.id,
            transaction_id=valid_transaction.id,
            initial_amount=300,
            remaining_amount=300,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),  # Not expired
            is_active=True,
        )
        session.add(valid_balance)

        await session.commit()

        # Mock Stripe API responses
        mock_stripe_subscription = MagicMock()
        mock_stripe_subscription.id = subscription.platform_subscription_id
        mock_stripe_subscription.current_period_start = int(
            datetime.now(timezone.utc).timestamp()
        )
        mock_stripe_subscription.current_period_end = int(
            (datetime.now(timezone.utc) + timedelta(days=30)).timestamp()
        )

        # Create a mock invoice
        mock_invoice = MagicMock()
        mock_invoice.id = "invoice_test123"
        mock_invoice.subscription = subscription.platform_subscription_id

        # Process the invoice payment
        with patch(
            "stripe.Subscription.retrieve", return_value=mock_stripe_subscription
        ):
            await stripe_service.handle_invoice_payment_succeeded(mock_invoice)

        # Query the database to verify the results
        rollover_query = select(CreditTransaction).where(
            CreditTransaction.user_id == user.id,
            CreditTransaction.credit_metadata.contains({"is_rollover": True}),
        )
        result = await session.execute(rollover_query)
        rollover_transactions = result.scalars().all()

        # Should have 1 rollover transaction
        assert len(rollover_transactions) == 1

        # Verify only the valid balance was rolled over
        rollover_transaction = rollover_transactions[0]
        assert rollover_transaction.amount == 300  # Only the valid balance amount
        assert rollover_transaction.amount != 800  # Not both balances combined
