from typing import AsyncGenerator, Dict, Generator

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.auth_handler import AuthHandler
from app.database import db_session
from app.models import User


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting a database session.

    Returns:
        AsyncSession: Database session
    """
    # db_session is already an async generator, so we just need to yield from it
    async for session in db_session():
        yield session


async def get_current_user(
    email: str = Depends(AuthHandler()), session: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency for getting the current authenticated user.

    Args:
        email: Email of the authenticated user (from AuthHandler)
        session: Database session

    Returns:
        User: User object
    """
    query = select(User).where(User.email == email)
    result = await session.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return user


async def get_current_admin_user(user: User = Depends(get_current_user)) -> Dict:
    """
    Dependency for getting the current admin user.

    Args:
        user: User object (from get_current_user)

    Returns:
        Dict: User information

    Raises:
        HTTPException: If the user is not an admin
    """
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized. Admin access required.",
        )

    return {"email": user.email, "id": str(user.id), "is_admin": user.is_admin}
