import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app
from app.models import CreditTransaction, User, UserCreditBalance
from app.schemas import SsoUserLoginRequest


@pytest.mark.asyncio
async def test_signup_bonus_credits(client: TestClient, db_session: AsyncSession):
    """Test that users receive 100 credits as a signup bonus when they register"""
    # Create a test user
    test_user_data = {
        "name": "Test User",
        "email": "testuser@example.com",
        "password": "testpassword123",
    }

    # Register the user
    response = client.post("/api/auth/register", json=test_user_data)
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Verify the user was created
    user_query = select(User).where(User.email == test_user_data["email"])
    user_result = await db_session.execute(user_query)
    user = user_result.scalar_one_or_none()
    assert user is not None

    # Verify a credit transaction was created
    transaction_query = select(CreditTransaction).where(
        CreditTransaction.user_id == user.id,
        CreditTransaction.amount == 100,
        CreditTransaction.description == "Signup bonus credits",
    )
    transaction_result = await db_session.execute(transaction_query)
    transaction = transaction_result.scalar_one_or_none()
    assert transaction is not None

    # Verify a credit balance was created
    balance_query = select(UserCreditBalance).where(
        UserCreditBalance.user_id == user.id, UserCreditBalance.initial_amount == 100
    )
    balance_result = await db_session.execute(balance_query)
    balance = balance_result.scalar_one_or_none()
    assert balance is not None
    assert balance.remaining_amount == 100


@pytest.mark.asyncio
async def test_sso_signup_bonus_credits(client: TestClient, db_session: AsyncSession):
    """Test that users receive 100 credits as a signup bonus when they register via SSO"""
    # Create a test SSO user
    test_sso_user_data = {
        "name": "SSO Test User",
        "email": "sso_testuser@example.com",
        "image": "https://example.com/profile.jpg",
        "provider": "google",
        "provider_id": "12345",
        "invite_code": None,
    }

    # Register the user via SSO
    response = client.post("/api/auth/sso", json=test_sso_user_data)
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Verify the user was created
    user_query = select(User).where(User.email == test_sso_user_data["email"])
    user_result = await db_session.execute(user_query)
    user = user_result.scalar_one_or_none()
    assert user is not None

    # Verify a credit transaction was created
    transaction_query = select(CreditTransaction).where(
        CreditTransaction.user_id == user.id,
        CreditTransaction.amount == 100,
        CreditTransaction.description == "Signup bonus credits",
    )
    transaction_result = await db_session.execute(transaction_query)
    transaction = transaction_result.scalar_one_or_none()
    assert transaction is not None

    # Verify the transaction metadata includes the SSO source
    assert transaction.credit_metadata.get("source") == "sso"

    # Verify a credit balance was created
    balance_query = select(UserCreditBalance).where(
        UserCreditBalance.user_id == user.id, UserCreditBalance.initial_amount == 100
    )
    balance_result = await db_session.execute(balance_query)
    balance = balance_result.scalar_one_or_none()
    assert balance is not None
    assert balance.remaining_amount == 100
