#!/usr/bin/env python
"""
Script to retrieve all active subscriptions from Stripe and print details.
This script will list customer name, email, subscription name, subscription ID,
product ID, price ID, and when the subscription ends.

It can also migrate subscriptions from old products to new credit-based products.

Usage:
    ./list_stripe_subscriptions.py [--period=monthly|yearly] [--export=filename.csv] [--all]
    ./list_stripe_subscriptions.py --migrate [--email=user@example.com] [--dry-run] [--execute]

Options:
    --period=TYPE       Filter subscriptions by period type (monthly or yearly)
    --export=FILE       Export results to a CSV file
    --all               Include all subscriptions (not just active ones)
    --migrate           Show migration plan for subscriptions
    --email=EMAIL       Only process subscriptions for this email address
    --dry-run           Show what would be migrated without making changes (default)
    --execute           Actually perform the migration
"""

# Suppress deprecation warnings about session.execute()
import warnings

warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message=".*You probably want to use.*session.exec.*",
)

import csv
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import stripe
from sqlalchemy import insert, select, text
from tabulate import tabulate

from app.config import settings
from app.database import SessionLocal
from app.models import (
    CreditPackage,
    CreditTransaction,
    SubscriptionPeriod,
    TransactionSource,
    TransactionType,
    User,
    UserCreditBalance,
    UserSubscription,
)

# Define the mapping from old product IDs to new product IDs
PRODUCT_MIGRATION_MAPPING = {
    # Monthly subscriptions to Gold Monthly
    "prod_QdeUkHNxJVwpf1": "prod_RsbjJC0GLvf99b",  # IAH Premium Monthly -> Gold Monthly
    "prod_RV4aKv0h2ERqv4": "prod_RsbjJC0GLvf99b",  # IAH Monthly Credit -> Gold Monthly
    # Yearly subscriptions to Platinum Yearly
    "prod_RV4cp3ilrjJEvo": "prod_RssteGejw19lTo",  # IAH Yearly Credit -> Platinum Yearly
    "prod_RGaPe8N5kfU2X4": "prod_RssteGejw19lTo",  # IAH Yearly Premium -> Platinum Yearly
    "prod_RK82YzwqR8vXx7": "prod_RssteGejw19lTo",  # IAH Yearly Premium -> Platinum Yearly
}


def parse_args():
    """Parse command line arguments."""
    args = {
        "period": None,
        "export": None,
        "all": False,
        "migrate": False,
        "email": None,
        "dry_run": True,
        "execute": False,
    }

    for arg in sys.argv[1:]:
        if arg.startswith("--period="):
            period = arg.split("=")[1].lower()
            if period in ["monthly", "yearly"]:
                args["period"] = period
            else:
                print(f"Invalid period: {period}. Must be 'monthly' or 'yearly'")
                sys.exit(1)
        elif arg.startswith("--export="):
            args["export"] = arg.split("=")[1]
        elif arg.startswith("--email="):
            args["email"] = arg.split("=")[1]
        elif arg == "--all":
            args["all"] = True
        elif arg == "--migrate":
            args["migrate"] = True
        elif arg == "--dry-run":
            args["dry_run"] = True
            args["execute"] = False
        elif arg == "--execute":
            args["dry_run"] = False
            args["execute"] = True
        elif arg in ["--help", "-h"]:
            print(__doc__)
            sys.exit(0)

    return args


def format_datetime(timestamp):
    """Format a Unix timestamp to a readable datetime string."""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def determine_subscription_period(price):
    """Determine subscription period from price object."""
    # First check the price recurring interval
    if hasattr(price, "recurring") and price.recurring:
        interval = price.recurring.get("interval")
        if interval == "year":
            return "yearly"
        elif interval == "month":
            return "monthly"

    # If not found in recurring, check product name
    if hasattr(price, "product") and price.product:
        product_name = price.product.name.lower()
        if "yearly" in product_name or "annual" in product_name:
            return "yearly"
        elif "monthly" in product_name:
            return "monthly"

    # If still not found, check price metadata
    if hasattr(price, "metadata") and price.metadata:
        if price.metadata.get("period") in ["yearly", "monthly"]:
            return price.metadata.get("period")

    # Default to unknown
    return "unknown"


async def get_user_by_email(session, email):
    """Get user details from the database by email."""
    query = select(User).where(User.email == email)
    # Use session.execute with scalar_one_or_none to get the actual model object
    result = await session.execute(query)
    user = result.scalar_one_or_none()

    # Debug output to understand the structure
    print(f"User type: {type(user)}")

    return user


async def get_package_by_product_id(session, product_id):
    """Get package details from the database by Stripe product ID."""
    query = select(CreditPackage).where(CreditPackage.stripe_product_id == product_id)
    # Use session.execute with scalar_one_or_none to get the actual model object
    result = await session.execute(query)
    package = result.scalar_one_or_none()

    # Debug output
    if package:
        print(f"Package type: {type(package)}")

    return package


async def get_user_subscription(session, user_id, platform_subscription_id):
    """Get user subscription from the database."""
    query = select(UserSubscription).where(
        UserSubscription.user_id == user_id,
        UserSubscription.platform_subscription_id == platform_subscription_id,
    )
    # Use session.execute with scalar_one_or_none to get the actual model object
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_user_credit_balance(session, user_id):
    """Get user's current credit balance."""
    query = select(UserCreditBalance).where(
        UserCreditBalance.user_id == user_id, UserCreditBalance.is_active == True
    )
    # Use session.execute with scalars to get the actual model objects
    result = await session.execute(query)
    balances = result.scalars().all()

    total_balance = 0
    for balance in balances:
        total_balance += balance.remaining_amount

    return total_balance


async def update_stripe_subscription(subscription_id, new_price_id):
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


async def create_migration_log(
    session, user_id, old_package_id, new_package_id, subscription_id
):
    """Create a log entry for the migration."""
    try:
        # Create a table for migration logs if it doesn't exist
        create_table_sql = text(
            """
            CREATE TABLE IF NOT EXISTS subscription_migration_logs (
                id UUID PRIMARY KEY,
                user_id UUID NOT NULL,
                old_package_id UUID,
                new_package_id UUID NOT NULL,
                stripe_subscription_id TEXT NOT NULL,
                migration_date TIMESTAMP WITH TIME ZONE NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            )
        """
        )
        # For raw SQL, we still use session.execute
        await session.execute(create_table_sql)

        # Insert the log entry
        log_id = uuid.uuid4()
        insert_sql = text(
            """
            INSERT INTO subscription_migration_logs 
            (id, user_id, old_package_id, new_package_id, stripe_subscription_id, migration_date)
            VALUES (:id, :user_id, :old_package_id, :new_package_id, :subscription_id, :migration_date)
        """
        )
        # For raw SQL, we still use session.execute
        await session.execute(
            insert_sql,
            {
                "id": log_id,
                "user_id": user_id,
                "old_package_id": old_package_id,
                "new_package_id": new_package_id,
                "subscription_id": subscription_id,
                "migration_date": datetime.now(timezone.utc),
            },
        )

        return True
    except Exception as e:
        print(f"Error creating migration log: {str(e)}")
        return False


def list_stripe_subscriptions():
    """Retrieve all active subscriptions from Stripe and print details."""
    # Parse command line arguments
    args = parse_args()

    # Initialize Stripe with API key
    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        # If migration mode is enabled, handle that separately
        if args["migrate"]:
            import asyncio

            asyncio.run(migrate_subscriptions(args))
            return

        print("Fetching subscriptions from Stripe...")

        # Set up query parameters
        query_params = {"limit": 100}  # Maximum allowed by Stripe

        if not args["all"]:
            query_params["status"] = "active"

        # If email is specified, get customer ID first
        if args["email"]:
            customers = stripe.Customer.list(email=args["email"])
            if not customers.data:
                print(f"No customer found with email: {args['email']}")
                return

            customer_ids = [customer.id for customer in customers.data]
            print(f"Found {len(customer_ids)} customers with email {args['email']}")

            # We'll process each customer's subscriptions separately
            subscription_data = []

            for customer_id in customer_ids:
                customer_params = query_params.copy()
                customer_params["customer"] = customer_id

                # List subscriptions for this customer
                subscriptions_response = stripe.Subscription.list(**customer_params)

                # Process subscriptions
                subscription_data.extend(
                    process_subscriptions(subscriptions_response, args)
                )
        else:
            # Prepare data for tabulation
            subscription_data = []

            # Handle pagination to get all subscriptions
            has_more = True
            starting_after = None

            while has_more:
                # Add pagination parameter if we're not on the first page
                if starting_after:
                    query_params["starting_after"] = starting_after

                # List subscriptions
                subscriptions_response = stripe.Subscription.list(**query_params)

                # Process this page of subscriptions
                page_data = process_subscriptions(subscriptions_response, args)
                subscription_data.extend(page_data)

                # Check if there are more pages
                has_more = subscriptions_response.get("has_more", False)

                # If there are more pages, get the ID of the last subscription to use as starting_after
                if has_more and subscriptions_response.get("data"):
                    starting_after = subscriptions_response.get("data")[-1].id
                    print(
                        f"Fetching next page of subscriptions after {starting_after}..."
                    )

        if not subscription_data:
            print("No subscriptions found matching the criteria.")
            return

        # Define headers
        headers = [
            "Customer Name",
            "Email",
            "Subscription Name",
            "Period",
            "Subscription ID",
            "Product ID",
            "Price ID",
            "Status",
            "Created Date",
            "Period Start",
            "Period End",
            "Cancel at Period End",
        ]

        # Print the data in a table format
        print(tabulate(subscription_data, headers=headers, tablefmt="grid"))
        print(f"Total subscriptions: {len(subscription_data)}")

        # Export to CSV if requested
        if args["export"]:
            with open(args["export"], "w", newline="") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(headers)
                writer.writerows(subscription_data)
            print(f"Data exported to {args['export']}")

    except Exception as e:
        print(f"Error retrieving subscriptions: {str(e)}")


def process_subscriptions(subscriptions_response, args):
    """Process a page of subscriptions and return formatted data."""
    subscription_data = []

    for subscription in subscriptions_response.get("data", []):
        # Get customer details
        try:
            customer = stripe.Customer.retrieve(subscription.customer)
        except Exception as e:
            print(f"Error retrieving customer {subscription.customer}: {str(e)}")
            customer_name = "Unknown"
            customer_email = "Unknown"
        else:
            customer_name = customer.name or "No Name"
            customer_email = customer.email or "No Email"

        # Get subscription items
        for item in subscription.get("items", {}).get("data", []):
            # Retrieve price with product expanded
            try:
                price = stripe.Price.retrieve(item.price.id, expand=["product"])
                product = price.product
                product_name = product.name
                product_id = product.id

                # Determine subscription period from price
                subscription_period = determine_subscription_period(price)

            except Exception as e:
                print(f"Error retrieving price {item.price.id}: {str(e)}")
                product_name = "Unknown"
                product_id = "Unknown"
                subscription_period = "unknown"

            # Skip if filtering by period and this doesn't match
            if args["period"] and subscription_period != args["period"]:
                continue

            # Format dates
            try:
                end_date = format_datetime(subscription.current_period_end)
                start_date = format_datetime(subscription.current_period_start)
                created_date = format_datetime(subscription.created)
            except Exception as e:
                print(f"Error formatting dates: {str(e)}")
                end_date = "Unknown"
                start_date = "Unknown"
                created_date = "Unknown"

            # Add to data list
            row = [
                customer_name,
                customer_email,
                product_name,
                subscription_period,
                subscription.id,
                product_id,
                item.price.id,
                subscription.status,
                created_date,
                start_date,
                end_date,
                "Yes" if subscription.get("cancel_at_period_end", False) else "No",
            ]

            subscription_data.append(row)

    return subscription_data


async def migrate_subscriptions(args):
    """Migrate subscriptions from old products to new credit-based products."""
    print("Analyzing subscriptions for migration...")

    # Initialize Stripe with API key
    stripe.api_key = settings.STRIPE_SECRET_KEY

    # Initialize database session
    session = SessionLocal()

    try:
        # Set up query parameters
        query_params = {"limit": 100, "status": "active"}

        # If email is specified, get customer ID first
        if args["email"]:
            customers = stripe.Customer.list(email=args["email"])
            if not customers.data:
                print(f"No customer found with email: {args['email']}")
                return

            customer_ids = [customer.id for customer in customers.data]
            print(f"Found {len(customer_ids)} customers with email {args['email']}")

            # We'll process each customer's subscriptions separately
            all_subscriptions = []

            for customer_id in customer_ids:
                customer_params = query_params.copy()
                customer_params["customer"] = customer_id

                # List subscriptions for this customer
                subscriptions_response = stripe.Subscription.list(**customer_params)
                all_subscriptions.extend(subscriptions_response.get("data", []))
        else:
            # Handle pagination to get all subscriptions
            all_subscriptions = []
            has_more = True
            starting_after = None

            while has_more:
                # Add pagination parameter if we're not on the first page
                if starting_after:
                    query_params["starting_after"] = starting_after

                # List subscriptions
                subscriptions_response = stripe.Subscription.list(**query_params)

                # Add this page of subscriptions
                all_subscriptions.extend(subscriptions_response.get("data", []))

                # Check if there are more pages
                has_more = subscriptions_response.get("has_more", False)

                # If there are more pages, get the ID of the last subscription to use as starting_after
                if has_more and subscriptions_response.get("data"):
                    starting_after = subscriptions_response.get("data")[-1].id
                    print(
                        f"Fetching next page of subscriptions after {starting_after}..."
                    )

        # Prepare migration data
        migration_data = []

        for subscription in all_subscriptions:
            # Get customer details
            try:
                customer = stripe.Customer.retrieve(subscription.customer)
                customer_name = customer.name or "No Name"
                customer_email = customer.email or "No Email"
            except Exception as e:
                print(f"Error retrieving customer {subscription.customer}: {str(e)}")
                continue

            # Get subscription items
            for item in subscription.get("items", {}).get("data", []):
                # Retrieve price with product expanded
                try:
                    price = stripe.Price.retrieve(item.price.id, expand=["product"])
                    product = price.product
                    product_id = product.id
                    product_name = product.name
                except Exception as e:
                    print(f"Error retrieving price {item.price.id}: {str(e)}")
                    continue

                # Check if this product needs migration
                if product_id in PRODUCT_MIGRATION_MAPPING:
                    # Get the new product ID
                    new_product_id = PRODUCT_MIGRATION_MAPPING[product_id]

                    # Get the new package from the database
                    new_package = await get_package_by_product_id(
                        session, new_product_id
                    )

                    if not new_package:
                        print(
                            f"Error: New package not found for product ID {new_product_id}"
                        )
                        continue

                    # Get the user from the database
                    user = await get_user_by_email(session, customer_email)

                    if not user:
                        print(f"Error: User not found for email {customer_email}")
                        continue

                    # Print user details for debugging
                    print(f"Found user: {user}")

                    # Add to migration data
                    migration_data.append(
                        {
                            "subscription_id": subscription.id,
                            "customer_name": customer_name,
                            "customer_email": customer_email,
                            "user_id": str(
                                user.id
                            ),  # Convert UUID to string to avoid issues
                            "current_product_id": product_id,
                            "current_product_name": product_name,
                            "current_price_id": item.price.id,
                            "new_product_id": new_product_id,
                            "new_package_id": str(
                                new_package.id
                            ),  # Convert UUID to string
                            "new_package_name": new_package.name,
                            "new_price_id": new_package.stripe_price_id,
                            "new_package_credits": new_package.credits,
                            "subscription_period": determine_subscription_period(price),
                            "current_period_end": subscription.current_period_end,
                            "current_period_start": subscription.current_period_start,
                            "stripe_subscription": subscription,
                        }
                    )

        if not migration_data:
            print("No subscriptions found that need migration.")
            return

        # Prepare tabular data for display
        table_data = []
        for item in migration_data:
            table_data.append(
                [
                    item["customer_name"],
                    item["customer_email"],
                    item["current_product_name"],
                    item["new_package_name"],
                    item["subscription_id"],
                    format_datetime(item["current_period_end"]),
                ]
            )

        # Print the migration plan
        headers = [
            "Customer Name",
            "Email",
            "Current Product",
            "New Package",
            "Subscription ID",
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
                    f"Migrating {item['customer_email']} from {item['current_product_name']} to {item['new_package_name']}..."
                )

                # Update the subscription in Stripe
                success, result = await update_stripe_subscription(
                    item["subscription_id"], item["new_price_id"]
                )

                if not success:
                    print(f"  Error updating Stripe subscription: {result}")
                    failure_count += 1
                    continue

                # Get or create user subscription in the database
                user_subscription = await get_user_subscription(
                    session, item["user_id"], item["subscription_id"]
                )

                previous_package_id = None

                if not user_subscription:
                    print(f"  Creating new user subscription record in database")
                    # Create new subscription record
                    user_subscription = UserSubscription(
                        user_id=item["user_id"],
                        package_id=item["new_package_id"],
                        platform="stripe",
                        platform_subscription_id=item["subscription_id"],
                        status="active",
                        current_period_start=datetime.fromtimestamp(
                            result.current_period_start, tz=timezone.utc
                        ),
                        current_period_end=datetime.fromtimestamp(
                            result.current_period_end, tz=timezone.utc
                        ),
                        cancel_at_period_end=result.cancel_at_period_end,
                        credits_per_period=item["new_package_credits"],
                        billing_cycle=item["subscription_period"],
                        credit_allocation_cycle="monthly",
                    )
                else:
                    print(f"  Updating existing user subscription record in database")
                    # Store the previous package ID
                    previous_package_id = user_subscription.package_id
                    user_subscription.previous_package_id = previous_package_id

                    # Update to the new package
                    user_subscription.package_id = item["new_package_id"]

                    # Update credits per period based on the new package
                    user_subscription.credits_per_period = item["new_package_credits"]

                session.add(user_subscription)
                await session.flush()  # Flush to get the ID if it's a new record

                # Create a credit transaction for the initial credits
                print(f"  Creating credit transaction for initial credits")

                # Get current balance
                current_balance = await get_user_credit_balance(
                    session, item["user_id"]
                )
                new_balance = current_balance + item["new_package_credits"]

                # Create transaction
                transaction = CreditTransaction(
                    user_id=item["user_id"],
                    transaction_type=TransactionType.CREDIT,
                    transaction_source=TransactionSource.SUBSCRIPTION_RENEWAL,  # Use an existing transaction source
                    amount=item["new_package_credits"],
                    balance_after=new_balance,
                    description=f"Initial credit allocation for migration to {item['new_package_name']}",
                    subscription_id=str(user_subscription.id),
                    package_id=item["new_package_id"],
                    credit_metadata={
                        "migration_date": datetime.now(timezone.utc).isoformat(),
                        "previous_package_id": (
                            str(previous_package_id) if previous_package_id else None
                        ),
                        "is_migration": True,  # Add a flag to identify migration transactions
                    },
                )
                session.add(transaction)
                await session.flush()  # Flush to get the transaction ID

                # Calculate expiration date based on subscription period
                if item["subscription_period"] == "monthly":
                    expiration_date = datetime.fromtimestamp(
                        item["current_period_end"], tz=timezone.utc
                    )
                else:  # yearly
                    # For yearly subscriptions, credits expire in 30 days
                    expiration_date = datetime.now(timezone.utc) + timedelta(days=30)

                # Create credit balance
                credit_balance = UserCreditBalance(
                    user_id=item["user_id"],
                    package_id=item["new_package_id"],
                    transaction_id=transaction.id,
                    initial_amount=item["new_package_credits"],
                    remaining_amount=item["new_package_credits"],
                    expires_at=expiration_date,
                    is_active=True,
                )
                session.add(credit_balance)

                # Log the migration
                await create_migration_log(
                    session,
                    item["user_id"],
                    previous_package_id,
                    item["new_package_id"],
                    item["subscription_id"],
                )

                success_count += 1
                print(f"  Success: Database updated with new subscription and credits")

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
        import traceback

        traceback.print_exc()
    finally:
        await session.close()


if __name__ == "__main__":
    list_stripe_subscriptions()
