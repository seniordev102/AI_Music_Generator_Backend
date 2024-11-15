#!/usr/bin/env python
"""
Script to migrate existing subscriptions to the new credit-based subscription model.
This script will:
1. Identify old subscriptions that need to be migrated
2. Map monthly subscriptions to Gold monthly
3. Map yearly subscriptions to Platinum yearly
4. Preview the changes
5. Optionally perform the migration

Usage:
    ./migrate_to_credit_subscriptions.py [--dry-run] [--execute] [--export=filename.csv]

Options:
    --dry-run       Only show what would be migrated without making changes (default)
    --execute       Actually perform the migration
    --export=FILE   Export migration plan to a CSV file
"""

import asyncio
import csv
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import stripe
from sqlalchemy import select
from tabulate import tabulate

from app.config import settings
from app.database import SessionLocal
from app.models import CreditPackage, SubscriptionPeriod, User, UserSubscription

# Define the mapping from old to new packages
# This should be updated based on your specific package IDs
MIGRATION_MAPPING = {
    "monthly": {
        "target_name": "Gold",
        "target_period": SubscriptionPeriod.MONTHLY,
        "target_package_id": None,  # Will be populated at runtime
    },
    "yearly": {
        "target_name": "Platinum",
        "target_period": SubscriptionPeriod.YEARLY,
        "target_package_id": None,  # Will be populated at runtime
    },
}


async def get_package_by_name_and_period(
    session, name: str, period: SubscriptionPeriod
):
    """Get package details from the database by name and subscription period."""
    query = select(CreditPackage).where(
        CreditPackage.name == name,
        CreditPackage.subscription_period == period,
        CreditPackage.is_subscription == True,
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_user_by_id(session, user_id):
    """Get user details from the database by ID."""
    query = select(User).where(User.id == user_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_active_subscriptions(session):
    """Get all active subscriptions from the database."""
    query = select(UserSubscription).where(UserSubscription.status == "active")
    result = await session.execute(query)
    return result.scalars().all()


async def get_package_by_id(session, package_id):
    """Get package details from the database by ID."""
    query = select(CreditPackage).where(CreditPackage.id == package_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()


def parse_args():
    """Parse command line arguments."""
    args = {"dry_run": True, "execute": False, "export": None}

    for arg in sys.argv[1:]:
        if arg == "--dry-run":
            args["dry_run"] = True
            args["execute"] = False
        elif arg == "--execute":
            args["dry_run"] = False
            args["execute"] = True
        elif arg.startswith("--export="):
            args["export"] = arg.split("=")[1]
        elif arg in ["--help", "-h"]:
            print(__doc__)
            sys.exit(0)

    return args


async def update_stripe_subscription(subscription_id: str, new_price_id: str):
    """Update a Stripe subscription to use the new price ID."""
    try:
        # Get the current subscription
        current_subscription = stripe.Subscription.retrieve(subscription_id)

        # Get the subscription item ID
        item_id = current_subscription["items"]["data"][0].id

        # Update the subscription
        updated_subscription = stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=False,
            proration_behavior="none",  # Don't prorate the change
            items=[
                {
                    "id": item_id,
                    "price": new_price_id,
                }
            ],
            metadata={
                "migrated_to_credit_based": "true",
                "migration_date": datetime.now(timezone.utc).isoformat(),
            },
        )

        return True, updated_subscription
    except Exception as e:
        return False, str(e)


async def migrate_subscriptions():
    """Migrate existing subscriptions to the new credit-based model."""
    # Parse command line arguments
    args = parse_args()

    # Initialize Stripe with API key
    stripe.api_key = settings.STRIPE_SECRET_KEY

    # Initialize database session
    session = SessionLocal()

    try:
        print("Analyzing subscriptions for migration...")

        # Get the target packages
        gold_monthly = await get_package_by_name_and_period(
            session, "Gold", SubscriptionPeriod.MONTHLY
        )
        platinum_yearly = await get_package_by_name_and_period(
            session, "Platinum", SubscriptionPeriod.YEARLY
        )

        if not gold_monthly:
            print("Error: Gold monthly package not found")
            return

        if not platinum_yearly:
            print("Error: Platinum yearly package not found")
            return

        # Update the mapping with actual package IDs
        MIGRATION_MAPPING["monthly"]["target_package_id"] = gold_monthly.id
        MIGRATION_MAPPING["yearly"]["target_package_id"] = platinum_yearly.id

        # Get all active subscriptions
        subscriptions = await get_active_subscriptions(session)

        # Prepare data for migration
        migration_data = []

        for subscription in subscriptions:
            # Get the current package
            current_package = await get_package_by_id(session, subscription.package_id)

            if not current_package:
                print(f"Warning: Package not found for subscription {subscription.id}")
                continue

            # Skip if this is already a credit-based package
            if current_package.name in ["Gold", "Platinum"]:
                continue

            # Get the user
            user = await get_user_by_id(session, subscription.user_id)

            if not user:
                print(f"Warning: User not found for subscription {subscription.id}")
                continue

            # Determine which new package to migrate to
            new_package = None
            if current_package.subscription_period == SubscriptionPeriod.MONTHLY:
                new_package = gold_monthly
                migration_type = "monthly"
            elif current_package.subscription_period == SubscriptionPeriod.YEARLY:
                new_package = platinum_yearly
                migration_type = "yearly"
            else:
                print(f"Warning: Unknown subscription period for {subscription.id}")
                continue

            # Add to migration data
            migration_data.append(
                {
                    "subscription_id": subscription.id,
                    "platform_subscription_id": subscription.platform_subscription_id,
                    "user_id": subscription.user_id,
                    "user_email": user.email,
                    "user_name": f"{user.first_name} {user.last_name}",
                    "current_package_id": subscription.package_id,
                    "current_package_name": current_package.name,
                    "current_period": current_package.subscription_period,
                    "new_package_id": new_package.id,
                    "new_package_name": new_package.name,
                    "new_period": new_package.subscription_period,
                    "platform": subscription.platform,
                    "status": subscription.status,
                    "current_period_end": subscription.current_period_end,
                    "migration_type": migration_type,
                }
            )

        if not migration_data:
            print("No subscriptions need migration.")
            return

        # Prepare tabular data for display
        table_data = []
        for item in migration_data:
            table_data.append(
                [
                    item["user_name"],
                    item["user_email"],
                    f"{item['current_package_name']} ({item['current_period']})",
                    f"{item['new_package_name']} ({item['new_period']})",
                    item["platform_subscription_id"],
                    item["platform"],
                    item["current_period_end"].strftime("%Y-%m-%d"),
                ]
            )

        # Print the migration plan
        headers = [
            "User Name",
            "Email",
            "Current Package",
            "New Package",
            "Subscription ID",
            "Platform",
            "Current Period End",
        ]

        print("\nMigration Plan:")
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        print(f"\nTotal subscriptions to migrate: {len(migration_data)}")

        # Export to CSV if requested
        if args["export"]:
            with open(args["export"], "w", newline="") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(headers)
                writer.writerows(table_data)
            print(f"Migration plan exported to {args['export']}")

        # Execute the migration if requested
        if args["execute"]:
            print("\nExecuting migration...")

            success_count = 0
            failure_count = 0

            for item in migration_data:
                print(
                    f"Migrating {item['user_email']} from {item['current_package_name']} to {item['new_package_name']}..."
                )

                # Update the subscription in Stripe if it's a Stripe subscription
                if item["platform"] == "stripe":
                    new_package = await get_package_by_id(
                        session, item["new_package_id"]
                    )

                    if not new_package or not new_package.stripe_price_id:
                        print(f"  Error: New package or price ID not found")
                        failure_count += 1
                        continue

                    success, result = await update_stripe_subscription(
                        item["platform_subscription_id"], new_package.stripe_price_id
                    )

                    if not success:
                        print(f"  Error updating Stripe subscription: {result}")
                        failure_count += 1
                        continue

                # Update the subscription in the database
                subscription_query = select(UserSubscription).where(
                    UserSubscription.id == item["subscription_id"]
                )
                subscription_result = await session.execute(subscription_query)
                subscription = subscription_result.scalar_one_or_none()

                if not subscription:
                    print(f"  Error: Subscription not found in database")
                    failure_count += 1
                    continue

                # Store the previous package ID
                subscription.previous_package_id = subscription.package_id

                # Update to the new package
                subscription.package_id = item["new_package_id"]

                # Update credits per period based on the new package
                new_package = await get_package_by_id(session, item["new_package_id"])
                subscription.credits_per_period = new_package.credits

                session.add(subscription)
                success_count += 1
                print(f"  Success: Database updated")

            # Commit the changes
            await session.commit()

            print(
                f"\nMigration complete: {success_count} succeeded, {failure_count} failed"
            )
        else:
            print("\nThis was a dry run. No changes were made.")
            print("To execute the migration, run with the --execute flag.")

    except Exception as e:
        print(f"Error during migration: {str(e)}")
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(migrate_subscriptions())
