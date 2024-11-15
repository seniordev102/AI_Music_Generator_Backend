import csv
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import stripe
from fastapi import Depends, HTTPException, status
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.http_response_model import PageMeta
from app.config import settings
from app.database import db_session
from app.models import (
    CreditPackage,
    CreditTransaction,
    TransactionSource,
    TransactionType,
    User,
    UserCreditBalance,
    UserSubscription,
)
from app.stripe.stripe_service import StripeService


class AdminSubscriptionService:
    def __init__(
        self,
        session: AsyncSession = Depends(db_session),
    ) -> None:
        self.session = session
        self.stripe_service = StripeService()
        stripe.api_key = settings.STRIPE_SECRET_KEY

    async def get_user_subscriptions(self):
        query = select(User)
        result = await self.session.execute(query)
        users = result.scalars().all()

        all_user_subscriptions = []

        for user in users:
            if user.stripe_customer_id:
                try:
                    subscriptions = await self.get_subscription_details(
                        user.stripe_customer_id
                    )

                    # Add user details to each subscription
                    for subscription in subscriptions:
                        # Check if this subscription is the active one recorded in the database
                        is_active_in_db = False
                        if (
                            user.active_subscription_id
                            == subscription["subscription_id"]
                        ):
                            is_active_in_db = True
                        elif user.subscription_id == subscription["subscription_id"]:
                            is_active_in_db = True

                        all_user_subscriptions.append(
                            {
                                "user_name": user.name,
                                "user_email": user.email,
                                "is_active_in_db": is_active_in_db,
                                **subscription,
                            }
                        )
                except Exception as e:
                    # Skip users with subscription errors
                    print(f"Error getting subscriptions for {user.email}: {str(e)}")
                    continue

        # Generate CSV file
        await self.generate_subscription_csv(all_user_subscriptions)

        return all_user_subscriptions

    async def generate_subscription_csv(self, user_subscriptions: List[Dict]):
        """
        Generate a CSV file with user subscription details.

        Args:
            user_subscriptions: List of dictionaries containing user and subscription details
        """
        if not user_subscriptions:
            return

        # Define CSV headers
        fieldnames = [
            "user_name",
            "user_email",
            "subscription_name",
            "next_invoice_date",
            "billing_interval",
            "amount",
            "is_canceled",
            "end_date",
            "subscription_id",
            "status",
            "is_active_in_db",
        ]

        # Write to CSV file in the root directory
        csv_path = "user_subscriptions.csv"

        with open(csv_path, mode="w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()

            for subscription in user_subscriptions:
                writer.writerow(subscription)

        return csv_path

    async def get_subscription_details(self, stripe_customer_id: str):
        """
        Get subscription details for a customer using their Stripe customer ID.

        Args:
            stripe_customer_id: The Stripe customer ID

        Returns:
            List of subscription details including:
            - Subscription name
            - Next invoice date
            - Billing interval (monthly/yearly)
            - Subscription amount
            - Cancellation status
            - End date if canceled
        """
        try:
            # Get all subscriptions for the customer
            subscriptions = stripe.Subscription.list(customer=stripe_customer_id)

            subscription_details = []

            for subscription in subscriptions.data:
                # Get the product details
                product = stripe.Product.retrieve(subscription.plan.product)

                # Calculate next invoice date
                current_period_end = datetime.fromtimestamp(
                    subscription.current_period_end
                )

                # Determine if subscription is monthly or yearly
                interval = subscription.plan.interval

                # Get subscription amount
                amount = subscription.plan.amount / 100  # Convert from cents to dollars

                # Check if subscription is canceled
                is_canceled = subscription.cancel_at_period_end

                # Get end date if canceled
                end_date = None
                if is_canceled:
                    end_date = datetime.fromtimestamp(subscription.cancel_at)

                subscription_details.append(
                    {
                        "subscription_name": product.name,
                        "next_invoice_date": current_period_end.strftime("%Y-%m-%d"),
                        "billing_interval": interval,
                        "amount": amount,
                        "is_canceled": is_canceled,
                        "end_date": end_date.strftime("%Y-%m-%d") if end_date else None,
                        "subscription_id": subscription.id,
                        "status": subscription.status,
                    }
                )

            return subscription_details

        except stripe.error.StripeError as e:
            # Handle Stripe API errors
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error retrieving subscription details: {str(e)}",
            )
        except Exception as e:
            # Handle other errors
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred: {str(e)}",
            )

    async def get_subscription_details_by_email(self, user_email: str):
        # Find the user by email
        query = select(User).where(User.email == user_email)
        result = await self.session.execute(query)
        user = result.scalars().first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with email {user_email} not found",
            )

        if not user.stripe_customer_id:
            return []  # User has no Stripe customer ID, so no subscriptions

        # Get subscription details using the Stripe customer ID
        subscriptions = await self.get_subscription_details(user.stripe_customer_id)

        # Add is_active_in_db field to each subscription
        for subscription in subscriptions:
            is_active_in_db = False
            if user.active_subscription_id == subscription["subscription_id"]:
                is_active_in_db = True
            elif user.subscription_id == subscription["subscription_id"]:
                is_active_in_db = True

            subscription["is_active_in_db"] = is_active_in_db

        return subscriptions

    async def get_subscription_details_by_customer_id(self, stripe_customer_id: str):
        """
        Get subscription details for a customer using their Stripe customer ID,
        and mark which subscription is the active one in the database.

        Args:
            stripe_customer_id: The Stripe customer ID

        Returns:
            List of subscription details with is_active_in_db field
        """
        # Find the user by stripe_customer_id
        query = select(User).where(User.stripe_customer_id == stripe_customer_id)
        result = await self.session.execute(query)
        user = result.scalars().first()

        if not user:
            # If user not found, just return the subscription details without marking active one
            return await self.get_subscription_details(stripe_customer_id)

        # Get subscription details
        subscriptions = await self.get_subscription_details(stripe_customer_id)

        # Add is_active_in_db field to each subscription
        for subscription in subscriptions:
            is_active_in_db = False
            if user.active_subscription_id == subscription["subscription_id"]:
                is_active_in_db = True
            elif user.subscription_id == subscription["subscription_id"]:
                is_active_in_db = True

            subscription["is_active_in_db"] = is_active_in_db

        return subscriptions

    async def migrate_subscriptions_to_credit_based(
        self, email: Optional[str] = None, execute: bool = False
    ):
        """
        Migrate subscriptions from old products to new credit-based products.

        Args:
            email: Optional email to filter subscriptions by user
            execute: Whether to actually perform the migration or just return the plan

        Returns:
            Dictionary with migration plan and results
        """
        # Define the mapping from old product IDs to new product IDs
        PRODUCT_MIGRATION_MAPPING = {
            "prod_REwtTLuZp5k3Mq": "prod_RuPUdEc5Eznx56",  # IAH Premium -> Platinum Yearly
            "prod_QHRS8dywoyyOw8": "prod_RuPUdEc5Eznx56",  # IAH Premium Yearly -> Platinum Yearly
            "prod_QHROkmuGhaJfBp": "prod_RuPT6johT6UCX6",  # IAH Premium Monthly -> Platinum Monthly
        }

        # Set up query parameters for Stripe
        query_params = {"limit": 100, "status": "active"}

        # Prepare migration data
        migration_data = []

        # If email is specified, get customer ID first
        if email:
            # Find the user by email
            query = select(User).where(User.email == email)
            result = await self.session.execute(query)
            user = result.scalar_one_or_none()

            if not user:
                return {
                    "success": False,
                    "message": f"No user found with email: {email}",
                    "migration_plan": [],
                    "results": [],
                }

            if not user.stripe_customer_id:
                return {
                    "success": False,
                    "message": f"User with email {email} has no Stripe customer ID",
                    "migration_plan": [],
                    "results": [],
                }

            # List subscriptions for this customer
            customers = [user.stripe_customer_id]
        else:
            # Get all users with stripe_customer_id
            query = select(User).where(User.stripe_customer_id.is_not(None))
            result = await self.session.execute(query)
            users = result.scalars().all()

            if not users:
                return {
                    "success": False,
                    "message": "No users found with Stripe customer IDs",
                    "migration_plan": [],
                    "results": [],
                }

            customers = [user.stripe_customer_id for user in users]

        # Process each customer
        for customer_id in customers:
            try:
                # List subscriptions for this customer
                subscriptions_response = stripe.Subscription.list(
                    customer=customer_id, **query_params
                )

                # Process each subscription
                for subscription in subscriptions_response.get("data", []):
                    # Get customer details
                    try:
                        customer = stripe.Customer.retrieve(subscription.customer)
                        customer_name = customer.name or "No Name"
                        customer_email = customer.email or "No Email"
                    except Exception as e:
                        print(
                            f"Error retrieving customer {subscription.customer}: {str(e)}"
                        )
                        continue

                    # Get user from database
                    query = select(User).where(User.email == customer_email)
                    result = await self.session.execute(query)
                    user = result.scalar_one_or_none()

                    if not user:
                        print(f"User not found for email {customer_email}")
                        continue

                    # Get subscription items
                    for item in subscription.get("items", {}).get("data", []):
                        # Retrieve price with product expanded
                        try:
                            price = stripe.Price.retrieve(
                                item.price.id, expand=["product"]
                            )
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
                            query = select(CreditPackage).where(
                                CreditPackage.stripe_product_id == new_product_id
                            )
                            result = await self.session.execute(query)
                            new_package = result.scalar_one_or_none()

                            if not new_package:
                                print(
                                    f"New package not found for product ID {new_product_id}"
                                )
                                continue

                            # Determine subscription period
                            if hasattr(price, "recurring") and price.recurring:
                                interval = price.recurring.get("interval")
                                if interval == "year":
                                    subscription_period = "yearly"
                                elif interval == "month":
                                    subscription_period = "monthly"
                                else:
                                    subscription_period = "unknown"
                            else:
                                subscription_period = "unknown"

                            # Add to migration data
                            migration_data.append(
                                {
                                    "subscription_id": subscription.id,
                                    "customer_name": customer_name,
                                    "customer_email": customer_email,
                                    "user_id": str(user.id),
                                    "current_product_id": product_id,
                                    "current_product_name": product_name,
                                    "current_price_id": item.price.id,
                                    "new_product_id": new_product_id,
                                    "new_package_id": str(new_package.id),
                                    "new_package_name": new_package.name,
                                    "new_price_id": new_package.stripe_price_id,
                                    "new_package_credits": new_package.credits,
                                    "subscription_period": subscription_period,
                                    "current_period_end": subscription.current_period_end,
                                    "current_period_start": subscription.current_period_start,
                                    "stripe_subscription": subscription,
                                }
                            )
            except Exception as e:
                print(f"Error processing customer {customer_id}: {str(e)}")
                continue

        # If no subscriptions need migration, return early
        if not migration_data:
            return {
                "success": True,
                "message": "No subscriptions found that need migration",
                "migration_plan": [],
                "results": [],
            }

        # Prepare tabular data for display
        migration_plan = []
        for item in migration_data:
            migration_plan.append(
                {
                    "customer_name": item["customer_name"],
                    "customer_email": item["customer_email"],
                    "current_product_name": item["current_product_name"],
                    "new_package_name": item["new_package_name"],
                    "subscription_id": item["subscription_id"],
                    "current_period_end": datetime.fromtimestamp(
                        item["current_period_end"], tz=timezone.utc
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                    "credits_to_allocate": item["new_package_credits"],
                }
            )

        # If not executing, just return the plan
        if not execute:
            return {
                "success": True,
                "message": "Migration plan generated (dry run)",
                "migration_plan": migration_plan,
                "results": [],
            }

        # Execute the migration
        migration_results = []

        for item in migration_data:
            try:
                print(
                    f"Migrating {item['customer_email']} from {item['current_product_name']} to {item['new_package_name']}..."
                )

                # Update the subscription in Stripe
                success, result = await self._update_stripe_subscription(
                    item["subscription_id"], item["new_price_id"]
                )

                if not success:
                    migration_results.append(
                        {
                            "customer_email": item["customer_email"],
                            "success": False,
                            "message": f"Error updating Stripe subscription: {result}",
                        }
                    )
                    continue

                # Get or create user subscription in the database
                user_subscription = await self._get_user_subscription(
                    item["user_id"], item["subscription_id"]
                )

                previous_package_id = None

                if not user_subscription:
                    print(f"Creating new user subscription record in database")
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
                    print(f"Updating existing user subscription record in database")
                    # Store the previous package ID
                    previous_package_id = user_subscription.package_id
                    user_subscription.previous_package_id = previous_package_id

                    # Update to the new package
                    user_subscription.package_id = item["new_package_id"]

                    # Update credits per period based on the new package
                    user_subscription.credits_per_period = item["new_package_credits"]

                self.session.add(user_subscription)
                await self.session.flush()  # Flush to get the ID if it's a new record

                # Create a credit transaction for the initial credits
                print(f"Creating credit transaction for initial credits")

                # Get current balance
                current_balance = await self._get_user_credit_balance(item["user_id"])
                new_balance = current_balance + item["new_package_credits"]

                # Create transaction
                transaction = CreditTransaction(
                    user_id=item["user_id"],
                    transaction_type=TransactionType.CREDIT,
                    transaction_source=TransactionSource.SUBSCRIPTION_RENEWAL,
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
                        "is_migration": True,
                    },
                )
                self.session.add(transaction)
                await self.session.flush()  # Flush to get the transaction ID

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
                self.session.add(credit_balance)

                # Log the migration
                await self._create_migration_log(
                    item["user_id"],
                    previous_package_id,
                    item["new_package_id"],
                    item["subscription_id"],
                )

                migration_results.append(
                    {
                        "customer_email": item["customer_email"],
                        "success": True,
                        "message": f"Successfully migrated to {item['new_package_name']} with {item['new_package_credits']} credits",
                    }
                )

            except Exception as e:
                migration_results.append(
                    {
                        "customer_email": item["customer_email"],
                        "success": False,
                        "message": f"Error during migration: {str(e)}",
                    }
                )

        # Commit the changes
        await self.session.commit()

        return {
            "success": True,
            "message": "Migration completed",
            "migration_plan": migration_plan,
            "results": migration_results,
        }

    async def _update_stripe_subscription(self, subscription_id, new_price_id):
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

    async def _get_user_subscription(self, user_id, platform_subscription_id):
        """Get user subscription from the database."""
        query = select(UserSubscription).where(
            UserSubscription.user_id == user_id,
            UserSubscription.platform_subscription_id == platform_subscription_id,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def _get_user_credit_balance(self, user_id):
        """Get user's current credit balance."""
        query = select(UserCreditBalance).where(
            UserCreditBalance.user_id == user_id, UserCreditBalance.is_active == True
        )
        result = await self.session.execute(query)
        balances = result.scalars().all()

        total_balance = 0
        for balance in balances:
            total_balance += balance.remaining_amount

        return total_balance

    async def _create_migration_log(
        self, user_id, old_package_id, new_package_id, subscription_id
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
            await self.session.execute(create_table_sql)

            # Insert the log entry
            log_id = uuid.uuid4()
            insert_sql = text(
                """
                INSERT INTO subscription_migration_logs 
                (id, user_id, old_package_id, new_package_id, stripe_subscription_id, migration_date)
                VALUES (:id, :user_id, :old_package_id, :new_package_id, :subscription_id, :migration_date)
            """
            )
            await self.session.execute(
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
