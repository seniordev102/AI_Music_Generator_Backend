#!/usr/bin/env python
"""
Script to update next_credit_allocation_date for yearly subscriptions.
This script sets the next allocation date based on the subscription start date,
calculating the same day of the next month.

Usage:
    python scripts/update_next_allocation_date.py [subscription_id]

If subscription_id is provided, only that subscription will be updated.
Otherwise, all eligible subscriptions will be updated.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal
from app.models import UserSubscription


async def update_next_allocation_date(subscription_id: Optional[str] = None):
    """Update next_credit_allocation_date for eligible subscriptions."""
    session = SessionLocal()
    try:
        # Build query for eligible subscriptions
        query = select(UserSubscription).where(
            and_(
                UserSubscription.status == "active",
                UserSubscription.billing_cycle == "yearly",
                UserSubscription.credit_allocation_cycle == "monthly",
            )
        )

        # If subscription_id is provided, filter by that
        if subscription_id:
            query = query.where(UserSubscription.id == subscription_id)

        result = await session.execute(query)
        subscriptions = result.scalars().all()

        if not subscriptions:
            print("No eligible subscriptions found.")
            return

        print(f"Found {len(subscriptions)} eligible subscriptions.")

        now = datetime.now(timezone.utc)

        # Update each subscription
        for subscription in subscriptions:
            print(f"\nSubscription ID: {subscription.id}")
            print(f"User ID: {subscription.user_id}")
            print(
                f"Current next_credit_allocation_date: {subscription.next_credit_allocation_date}"
            )
            print(f"Current period start: {subscription.current_period_start}")

            # Determine the reference date (last allocation date or subscription start date)
            reference_date = subscription.last_credit_allocation_date
            if reference_date is None:
                reference_date = subscription.current_period_start

            if reference_date is None:
                print(
                    f"Warning: Subscription {subscription.id} has no reference date for calculating next allocation"
                )
                continue

            print(f"Using reference date: {reference_date}")

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
                print(
                    f"Calculated next allocation date {next_allocation} is in the past, moving forward"
                )
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

            # Update the subscription
            subscription.next_credit_allocation_date = next_allocation
            session.add(subscription)

            print(f"Updated next_credit_allocation_date to: {next_allocation}")

        # Commit the changes
        await session.commit()
        print("\nSuccessfully updated next allocation dates.")

    finally:
        await session.close()


if __name__ == "__main__":
    # Get subscription_id from command line if provided
    subscription_id = None
    if len(sys.argv) > 1:
        subscription_id = sys.argv[1]
        print(f"Updating subscription with ID: {subscription_id}")

    asyncio.run(update_next_allocation_date(subscription_id))
