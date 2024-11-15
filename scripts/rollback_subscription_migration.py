#!/usr/bin/env python
"""
Script to rollback the subscription migration if needed.
This script will revert subscriptions that were migrated to the credit-based model
back to their original packages.

Usage:
    ./rollback_subscription_migration.py [--dry-run] [--execute] [--export=filename.csv] [--subscription-id=SUB_ID]

Options:
    --dry-run               Only show what would be rolled back without making changes (default)
    --execute               Actually perform the rollback
    --export=FILE           Export rollback plan to a CSV file
    --subscription-id=SUB_ID Only rollback a specific subscription ID
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
from app.models import CreditPackage, User, UserSubscription


async def get_user_by_id(session, user_id):
    """Get user details from the database by ID."""
    query = select(User).where(User.id == user_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_package_by_id(session, package_id):
    """Get package details from the database by ID."""
    query = select(CreditPackage).where(CreditPackage.id == package_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()


def parse_args():
    """Parse command line arguments."""
    args = {"dry_run": True, "execute": False, "export": None, "subscription_id": None}

    for arg in sys.argv[1:]:
        if arg == "--dry-run":
            args["dry_run"] = True
            args["execute"] = False
        elif arg == "--execute":
            args["dry_run"] = False
            args["execute"] = True
        elif arg.startswith("--export="):
            args["export"] = arg.split("=")[1]
        elif arg.startswith("--subscription-id="):
            args["subscription_id"] = arg.split("=")[1]
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
                "rollback_from_credit_based": "true",
                "rollback_date": datetime.now(timezone.utc).isoformat(),
            },
        )

        return True, updated_subscription
    except Exception as e:
        return False, str(e)


async def rollback_subscription_migration():
    """Rollback subscriptions that were migrated to the credit-based model."""
    # Parse command line arguments
    args = parse_args()

    # Initialize Stripe with API key
    stripe.api_key = settings.STRIPE_SECRET_KEY

    # Initialize database session
    session = SessionLocal()

    try:
        print("Analyzing subscriptions for rollback...")

        # Build the query to find migrated subscriptions
        query = select(UserSubscription).where(
            UserSubscription.previous_package_id != None,  # Has a previous package ID
            UserSubscription.status == "active",  # Is active
        )

        # If a specific subscription ID is provided, filter by it
        if args["subscription_id"]:
            query = query.where(
                UserSubscription.platform_subscription_id == args["subscription_id"]
            )

        # Execute the query
        result = await session.execute(query)
        subscriptions = result.scalars().all()

        if not subscriptions:
            print("No subscriptions found that can be rolled back.")
            return

        # Prepare data for rollback
        rollback_data = []

        for subscription in subscriptions:
            # Get the current package
            current_package = await get_package_by_id(session, subscription.package_id)

            if not current_package:
                print(
                    f"Warning: Current package not found for subscription {subscription.id}"
                )
                continue

            # Get the previous package
            previous_package = await get_package_by_id(
                session, subscription.previous_package_id
            )

            if not previous_package:
                print(
                    f"Warning: Previous package not found for subscription {subscription.id}"
                )
                continue

            # Get the user
            user = await get_user_by_id(session, subscription.user_id)

            if not user:
                print(f"Warning: User not found for subscription {subscription.id}")
                continue

            # Add to rollback data
            rollback_data.append(
                {
                    "subscription_id": subscription.id,
                    "platform_subscription_id": subscription.platform_subscription_id,
                    "user_id": subscription.user_id,
                    "user_email": user.email,
                    "user_name": f"{user.first_name} {user.last_name}",
                    "current_package_id": subscription.package_id,
                    "current_package_name": current_package.name,
                    "previous_package_id": subscription.previous_package_id,
                    "previous_package_name": previous_package.name,
                    "platform": subscription.platform,
                    "status": subscription.status,
                    "current_period_end": subscription.current_period_end,
                }
            )

        # Prepare tabular data for display
        table_data = []
        for item in rollback_data:
            table_data.append(
                [
                    item["user_name"],
                    item["user_email"],
                    item["current_package_name"],
                    item["previous_package_name"],
                    item["platform_subscription_id"],
                    item["platform"],
                    item["current_period_end"].strftime("%Y-%m-%d"),
                ]
            )

        # Print the rollback plan
        headers = [
            "User Name",
            "Email",
            "Current Package",
            "Previous Package",
            "Subscription ID",
            "Platform",
            "Current Period End",
        ]

        print("\nRollback Plan:")
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        print(f"\nTotal subscriptions to rollback: {len(rollback_data)}")

        # Export to CSV if requested
        if args["export"]:
            with open(args["export"], "w", newline="") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(headers)
                writer.writerows(table_data)
            print(f"Rollback plan exported to {args['export']}")

        # Execute the rollback if requested
        if args["execute"]:
            print("\nExecuting rollback...")

            success_count = 0
            failure_count = 0

            for item in rollback_data:
                print(
                    f"Rolling back {item['user_email']} from {item['current_package_name']} to {item['previous_package_name']}..."
                )

                # Update the subscription in Stripe if it's a Stripe subscription
                if item["platform"] == "stripe":
                    previous_package = await get_package_by_id(
                        session, item["previous_package_id"]
                    )

                    if not previous_package or not previous_package.stripe_price_id:
                        print(f"  Error: Previous package or price ID not found")
                        failure_count += 1
                        continue

                    success, result = await update_stripe_subscription(
                        item["platform_subscription_id"],
                        previous_package.stripe_price_id,
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

                # Restore the previous package ID
                subscription.package_id = subscription.previous_package_id

                # Clear the previous_package_id field
                subscription.previous_package_id = None

                # Update credits per period based on the previous package
                previous_package = await get_package_by_id(
                    session, item["previous_package_id"]
                )
                subscription.credits_per_period = previous_package.credits

                session.add(subscription)
                success_count += 1
                print(f"  Success: Database updated")

            # Commit the changes
            await session.commit()

            print(
                f"\nRollback complete: {success_count} succeeded, {failure_count} failed"
            )
        else:
            print("\nThis was a dry run. No changes were made.")
            print("To execute the rollback, run with the --execute flag.")

    except Exception as e:
        print(f"Error during rollback: {str(e)}")
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(rollback_subscription_migration())
