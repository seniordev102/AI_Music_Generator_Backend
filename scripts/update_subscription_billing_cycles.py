#!/usr/bin/env python
"""
Script to update existing subscriptions to set the correct billing cycle
based on the package's subscription period.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import join, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal
from app.models import CreditPackage, UserSubscription


async def update_subscription_billing_cycles():
    """Update subscription billing cycles based on package subscription period."""
    session = SessionLocal()
    try:
        # Query to join UserSubscription with CreditPackage
        query = (
            select(UserSubscription, CreditPackage)
            .join(CreditPackage, UserSubscription.package_id == CreditPackage.id)
            .where(UserSubscription.status == "active")
        )

        result = await session.execute(query)
        rows = result.all()

        updated_count = 0
        for subscription, package in rows:
            print(f"\nSubscription ID: {subscription.id}")
            print(f"User ID: {subscription.user_id}")
            print(f"Package Name: {package.name}")
            print(f"Package Period: {package.subscription_period}")
            print(f"Current Billing Cycle: {subscription.billing_cycle}")

            # Determine the correct billing cycle
            if (
                package.subscription_period == "yearly"
                and subscription.billing_cycle != "yearly"
            ):
                subscription.billing_cycle = "yearly"
                subscription.credit_allocation_cycle = (
                    "monthly"  # For yearly subscriptions, allocate monthly
                )
                session.add(subscription)
                updated_count += 1
                print(
                    f"Updated to: billing_cycle=yearly, credit_allocation_cycle=monthly"
                )
            elif (
                package.subscription_period == "monthly"
                and subscription.billing_cycle != "monthly"
            ):
                subscription.billing_cycle = "monthly"
                subscription.credit_allocation_cycle = "monthly"
                session.add(subscription)
                updated_count += 1
                print(
                    f"Updated to: billing_cycle=monthly, credit_allocation_cycle=monthly"
                )

        if updated_count > 0:
            await session.commit()
            print(f"\nUpdated {updated_count} subscriptions")
        else:
            print("\nNo subscriptions needed updating")

    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(update_subscription_billing_cycles())
