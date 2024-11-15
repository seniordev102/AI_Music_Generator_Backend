from datetime import datetime, timedelta, timezone
from typing import Dict, NamedTuple, Optional
from uuid import UUID

import stripe
import stripe.error
from fastapi import Depends, HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import db_session
from app.logger.logger import logger
from app.models import (
    CreditPackage,
    CreditTransaction,
    TransactionSource,
    TransactionType,
    User,
    UserCreditBalance,
    UserSubscription,
)


class SubscriptionWithPackage(NamedTuple):
    subscription: UserSubscription
    package: CreditPackage


class TransactionWithPackage(NamedTuple):
    transaction: CreditTransaction
    package: Optional[CreditPackage]


class StripeCreditManagementService:
    def __init__(
        self,
        session: AsyncSession = Depends(db_session),
    ) -> None:
        self.session = session

    async def _get_user_by_email(self, email: str) -> User:
        query = select(User).where(User.email == email)
        result = await self.session.execute(query)
        user: User = result.scalars().first()

        if not user:
            raise HTTPException(
                status_code=404, detail=f"User with email {email} not found"
            )

        return user

    async def _ensure_valid_stripe_customer(self, user: User, email) -> str:
        if not user.stripe_customer_id:
            customer = stripe.Customer.create(name=user.name, email=email)
            user.stripe_customer_id = customer["id"]
            await self.session.commit()
            return customer["id"]

        try:
            stripe.Customer.retrieve(user.stripe_customer_id)
            return user.stripe_customer_id
        except stripe.error.InvalidRequestError:
            customer = stripe.Customer.create(name=user.name, email=email)
            user.stripe_customer_id = customer["id"]
            await self.session.commit()
            return customer["id"]

    async def validate_coupon_by_name(self, coupon_name: str, original_price: float):
        try:
            # List coupons and filter by name
            coupons = stripe.Coupon.list(limit=100)
            coupon = next(
                (
                    coup
                    for coup in coupons.data
                    if coup.name and coup.name.lower() == coupon_name.lower()
                ),
                None,
            )

            if not coupon:
                return {
                    "valid": False,
                    "message": "Coupon not found",
                    "discounted_price": original_price,
                }

            if not coupon.valid:
                return {
                    "valid": False,
                    "message": "Coupon is no longer valid",
                    "discounted_price": original_price,
                }

            # Calculate discount based on coupon type
            if coupon.amount_off:  # Fixed amount discount
                discount = float(coupon.amount_off) / 100  # Convert cents to dollars
                discounted_price = max(0, original_price - discount)

            elif coupon.percent_off:  # Percentage discount
                discount = (coupon.percent_off / 100) * original_price
                discounted_price = original_price - discount

            else:
                return {
                    "valid": False,
                    "message": "Invalid coupon type",
                    "discounted_price": original_price,
                }

            return {
                "valid": True,
                "message": "Coupon applied successfully",
                "original_price": original_price,
                "discount": discount,
                "discounted_price": round(discounted_price, 2),
                "coupon_type": "amount_off" if coupon.amount_off else "percent_off",
            }

        except stripe.error.InvalidRequestError as e:
            return {
                "valid": False,
                "message": f"Stripe API error: {str(e)}",
                "discounted_price": original_price,
            }
        except Exception as e:
            return {
                "valid": False,
                "message": f"Error processing coupon: {str(e)}",
                "discounted_price": original_price,
            }

    async def _validate_coupon_and_amount(
        self, coupon_name: str, original_amount: float, payable_amount: float
    ):
        coupon_validation = await self.validate_coupon_by_name(
            coupon_name=coupon_name, original_price=original_amount
        )

        if not coupon_validation["valid"]:
            raise HTTPException(status_code=400, detail=coupon_validation["message"])

        if coupon_validation.get("discounted_price") != payable_amount:
            raise HTTPException(status_code=400, detail="Invalid payable amount")

    async def _check_active_subscription_stripe(
        self, customer_id: str
    ) -> Optional[stripe.Subscription]:
        try:
            subscriptions = stripe.Subscription.list(
                customer=customer_id,
                status="active",  # Only get active subscriptions
                limit=1,  # We only need to know if there's at least one
            )
            return subscriptions.data[0] if subscriptions.data else None
        except stripe.error.StripeError as e:
            raise HTTPException(
                status_code=400, detail=f"Failed to check subscription status: {str(e)}"
            )

    async def create_payment_intent(
        self,
        package_id: str,
        email: str,
        coupon_name: Optional[str] = None,
        payable_amount: float = 0,
        original_amount: float = 0,
        selected_payment_method_id: Optional[str] = None,
    ):
        query = select(CreditPackage).where(CreditPackage.id == package_id)
        result = await self.session.execute(query)
        package_details = result.scalars().first()

        if not package_details:
            raise HTTPException(status_code=404, detail="Invalid credit package")

        # Get the user by email
        user = await self._get_user_by_email(email)

        # Handle Stripe customer creation/validation
        user.stripe_customer_id = await self._ensure_valid_stripe_customer(user, email)

        # Validate coupon and amount
        if coupon_name:
            await self._validate_coupon_and_amount(
                coupon_name, original_amount, payable_amount
            )

        if payable_amount <= 0:
            raise HTTPException(status_code=400, detail="Invalid payable amount")

        # Common metadata for both subscription and one-time purchase
        metadata = {
            "package_id": package_id,
            "user_email": email,
            "credits": package_details.credits,
            "coupon_code": coupon_name if coupon_name else "",
        }

        if package_details.is_subscription:
            try:
                # First check if user has any active subscription from Stripe
                active_subscription = await self._check_active_subscription_stripe(
                    user.stripe_customer_id
                )
                if active_subscription:
                    raise HTTPException(
                        status_code=400,
                        detail="You already have an active subscription. Please cancel your existing subscription before starting a new one.",
                    )

                subscription = None
                payment_intent = None

                # Handle incomplete subscriptions
                subscription_list = stripe.Subscription.list(
                    customer=user.stripe_customer_id,
                    status="incomplete",  # Only check incomplete ones since we already checked active
                    expand=["data.latest_invoice.payment_intent"],
                    limit=1,
                )

                if subscription_list.data:
                    latest_subscription = subscription_list.data[0]

                    # Get subscription items
                    subscription_items_list = stripe.SubscriptionItem.list(
                        subscription=latest_subscription.id
                    )

                    # Check if any item matches the price ID
                    matching_price = any(
                        item.price.id == package_details.stripe_price_id
                        for item in subscription_items_list.data
                    )

                    if matching_price:
                        # Get payment intent from latest invoice
                        if (
                            hasattr(latest_subscription, "latest_invoice")
                            and latest_subscription.latest_invoice
                        ):
                            payment_intent = (
                                latest_subscription.latest_invoice.payment_intent
                            )

                            # If payment intent is completed or invalid, cancel subscription
                            if (
                                not payment_intent
                                or payment_intent.status == "succeeded"
                            ):
                                stripe.Subscription.delete(latest_subscription.id)
                                subscription = None
                            else:
                                subscription = latest_subscription
                    else:
                        # Price doesn't match, cancel incomplete subscription
                        stripe.Subscription.delete(latest_subscription.id)

                # Create new subscription if needed
                if not subscription:
                    new_subscription = stripe.Subscription.create(
                        customer=user.stripe_customer_id,
                        items=[{"price": package_details.stripe_price_id}],
                        payment_behavior="default_incomplete",
                        metadata=metadata,
                        expand=["latest_invoice.payment_intent"],
                    )
                    subscription = new_subscription
                    if (
                        hasattr(new_subscription, "latest_invoice")
                        and new_subscription.latest_invoice
                    ):
                        payment_intent = new_subscription.latest_invoice.payment_intent

            except stripe.error.StripeError as e:
                raise HTTPException(
                    status_code=400, detail=f"Failed to handle subscription: {str(e)}"
                )

        else:
            # One-time purchase flow remains unchanged
            params = {
                "amount": int(payable_amount * 100),
                "currency": "usd",
                "customer": user.stripe_customer_id,
                "metadata": metadata,
            }

            if selected_payment_method_id:
                params["payment_method"] = selected_payment_method_id
            else:
                params["setup_future_usage"] = "off_session"
                params["automatic_payment_methods"] = {"enabled": True}

            try:
                payment_intent = stripe.PaymentIntent.create(**params)
            except stripe.error.StripeError as e:
                raise HTTPException(
                    status_code=400, detail=f"Failed to create payment intent: {str(e)}"
                )

        return {
            "client_secret": payment_intent.client_secret if payment_intent else None,
            "customer_id": user.stripe_customer_id,
            "subscription_id": (
                subscription.id if package_details.is_subscription else None
            ),
        }

    async def remove_duplicate_payment_methods(
        self,
        email: str,
        keep_newest: bool = True,
    ) -> Dict:
        try:
            # Get user and verify stripe customer exists
            user = await self._get_user_by_email(email)
            if not user.stripe_customer_id:
                return {
                    "status": "skipped",
                    "message": "No Stripe customer found",
                    "removed_count": 0,
                    "remaining_cards": [],
                }

            # Get all payment methods for the customer
            payment_methods = stripe.PaymentMethod.list(
                customer=user.stripe_customer_id, type="card"
            )

            # Group payment methods by fingerprint
            fingerprint_groups = {}
            for pm in payment_methods.data:
                fingerprint = pm.card.fingerprint
                if fingerprint not in fingerprint_groups:
                    fingerprint_groups[fingerprint] = []
                fingerprint_groups[fingerprint].append(
                    {
                        "id": pm.id,
                        "created": pm.created,
                        "card": {
                            "brand": pm.card.brand,
                            "last4": pm.card.last4,
                            "exp_month": pm.card.exp_month,
                            "exp_year": pm.card.exp_year,
                            "fingerprint": fingerprint,
                        },
                    }
                )

            # Process each group to remove duplicates
            removed_count = 0
            remaining_cards = []

            for fingerprint, cards in fingerprint_groups.items():
                if len(cards) > 1:
                    # Sort cards by creation date
                    cards.sort(key=lambda x: x["created"], reverse=keep_newest)

                    # Keep the first card (newest or oldest based on keep_newest)
                    keeper = cards[0]
                    remaining_cards.append(keeper)

                    # Remove the rest
                    for card in cards[1:]:
                        try:
                            stripe.PaymentMethod.detach(card["id"])
                            removed_count += 1
                        except stripe.error.StripeError as e:
                            logger.debug(
                                f"Error removing payment method {card['id']}: {str(e)}"
                            )

                else:
                    # If only one card with this fingerprint, keep it
                    remaining_cards.append(cards[0])

            return {
                "status": "success",
                "message": f"Removed {removed_count} duplicate payment methods",
                "removed_count": removed_count,
                "remaining_cards": remaining_cards,
            }

        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=f"Stripe error: {str(e)}")
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to remove duplicate payment methods: {str(e)}",
            )

    async def _get_user_by_stripe_customer_id(self, customer_id: str) -> User:
        query = select(User).where(User.stripe_customer_id == customer_id)
        result = await self.session.execute(query)
        user: User = result.scalars().first()

        if not user:
            raise HTTPException(
                status_code=404, detail=f"User with email {customer_id} not found"
            )

        return user

    async def _get_or_create_balance(self, email: str) -> Dict:
        current_time = datetime.now(timezone.utc)
        user = await self._get_user_by_email(email)

        # Get all active balances
        query = select(UserCreditBalance).where(
            and_(
                UserCreditBalance.user_id == user.id,
                UserCreditBalance.is_active == True,
                UserCreditBalance.remaining_amount > 0,
                or_(
                    UserCreditBalance.expires_at > current_time,
                    UserCreditBalance.expires_at == None,
                ),
            )
        )

        result = await self.session.execute(query)
        balances = result.scalars().all()

        # Calculate total available credits
        total_balance = sum(balance.remaining_amount for balance in balances)
        total_earned = sum(balance.initial_amount for balance in balances)
        total_used = sum(
            balance.initial_amount - balance.remaining_amount for balance in balances
        )

        return {
            "current_balance": total_balance,
            "total_credits_earned": total_earned,
            "total_credits_used": total_used,
            "last_updated": current_time,
        }

    async def _get_package_details_by_id(self, package_id: str) -> CreditPackage:
        query = select(CreditPackage).where(CreditPackage.id == package_id)
        result = await self.session.execute(query)
        package = result.scalars().first()

        if not package:
            raise HTTPException(
                status_code=404, detail=f"Can not find the package for id {package_id}"
            )

        return package

    async def _add_credit_to_user_account(
        self,
        stripe_customer_id: str,
        package_id: str,
        payment_intent_id: str,
        metadata: Dict[str, str],
    ):
        try:
            logger.info(
                f"Starting credit addition for stripe_customer_id: {stripe_customer_id}"
            )
            logger.debug(
                f"Credit addition parameters - Package ID: {package_id}, Payment Intent: {payment_intent_id}"
            )

            # Check if a transaction with this payment_intent_id already exists (idempotency check)
            try:
                existing_transaction_query = select(CreditTransaction).where(
                    CreditTransaction.platform_transaction_id == payment_intent_id
                )
                existing_transaction_result = await self.session.execute(
                    existing_transaction_query
                )
                existing_transaction = existing_transaction_result.scalar_one_or_none()

                if existing_transaction:
                    logger.info(
                        f"Transaction with payment_intent_id {payment_intent_id} already exists. Skipping credit addition."
                    )
                    return
            except Exception as query_error:
                logger.error(f"Error in idempotency check query: {str(query_error)}")
                # If the query fails, we'll continue with the process
                # This is safer than potentially missing credit additions
                logger.info(
                    "Continuing with credit addition despite idempotency check failure"
                )

            # Get user details
            logger.info(
                f"Retrieving user details for stripe_customer_id: {stripe_customer_id}"
            )
            user = await self._get_user_by_stripe_customer_id(
                customer_id=stripe_customer_id
            )
            if not user:
                logger.error(
                    f"User not found for stripe_customer_id: {stripe_customer_id}"
                )
                raise ValueError(
                    f"No user found for stripe customer ID: {stripe_customer_id}"
                )
            logger.info(f"Found user with email: {user.email}")

            current_time = datetime.now(timezone.utc)
            logger.debug(f"Current UTC time: {current_time}")

            # Get package details
            logger.info(f"Retrieving package details for package_id: {package_id}")
            package = await self._get_package_details_by_id(package_id=package_id)
            if not package:
                logger.error(f"Package not found for ID: {package_id}")
                raise ValueError(f"No package found for ID: {package_id}")
            logger.info(f"Found package with credits: {package.credits}")

            # Calculate expiration
            expiration_date = None
            if package.expiration_days:
                expiration_date = current_time + timedelta(days=package.expiration_days)
                logger.info(f"Calculated expiration date: {expiration_date}")

            credited_amount = package.credits
            logger.info(f"Credit amount to be added: {credited_amount}")

            # Get current balance
            logger.info(f"Retrieving current balance for user: {user.email}")
            balance_info = await self._get_or_create_balance(email=user.email)
            current_balance = balance_info["current_balance"]
            new_balance = current_balance + credited_amount
            logger.info(
                f"Balance calculation - Current: {current_balance}, New: {new_balance}"
            )

            try:
                # Create transaction record
                logger.info("Creating credit transaction record")
                transaction = CreditTransaction(
                    user_id=str(user.id),
                    transaction_type=TransactionType.CREDIT,
                    transaction_source=TransactionSource.STRIPE,
                    amount=credited_amount,
                    balance_after=new_balance,
                    description=f"Credits purchased via Stripe payment",
                    platform_transaction_id=payment_intent_id,
                    package_id=package_id,
                    credit_metadata=metadata,
                )
                self.session.add(transaction)
                logger.debug("Added transaction to session")

                await self.session.flush()
                logger.info(f"Flushed transaction with ID: {transaction.id}")

                # Create credit balance record
                logger.info("Creating credit balance record")
                try:
                    credit_balance = UserCreditBalance(
                        user_id=user.id,
                        package_id=str(package_id),
                        transaction_id=transaction.id,
                        initial_amount=credited_amount,
                        remaining_amount=credited_amount,
                        expires_at=expiration_date,
                        is_active=True,
                    )
                    self.session.add(credit_balance)
                    logger.debug("Added credit balance to session")

                    await self.session.commit()
                    logger.info("Successfully committed credit addition transaction")

                except ValueError as ve:
                    logger.error(
                        f"Error creating UserCreditBalance - possible UUID format error: {str(ve)}"
                    )
                    await self.session.rollback()
                    raise

                except Exception as inner_e:
                    logger.error(
                        f"Error creating credit balance record: {str(inner_e)}"
                    )
                    await self.session.rollback()
                    raise

            except Exception as db_e:
                logger.error(f"Database error during credit addition: {str(db_e)}")
                logger.error("Transaction error details:", exc_info=True)
                await self.session.rollback()
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to add credits after payment: {str(db_e)}",
                )

        except Exception as outer_e:
            logger.error(f"Outer error in credit addition process: {str(outer_e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process credit addition: {str(outer_e)}",
            )

    async def handle_successful_payment(self, payment_intent: stripe.PaymentIntent):
        try:
            logger.info(
                f"Starting payment processing for payment_intent_id: {payment_intent.id}"
            )

            if not payment_intent.customer:
                logger.error(f"Payment intent {payment_intent.id} has no customer ID")
                raise ValueError("Customer ID is required")

            customer_id = payment_intent.customer
            amount = payment_intent.amount
            currency = payment_intent.currency
            metadata = payment_intent.metadata or {}
            payment_method = payment_intent.payment_method
            invoice_id = payment_intent.invoice
            amount_received = payment_intent.amount_received

            logger.info(
                f"Payment details - Customer: {customer_id}, Amount: {amount}, Currency: {currency}"
            )

            # Check if this payment is for a subscription (has an invoice_id)
            if invoice_id:
                logger.info(
                    f"Payment is for a subscription (invoice_id: {invoice_id}). Credits will be added by handle_invoice_payment_succeeded."
                )
                return

            # If we get here, this is a one-time payment, not a subscription
            logger.info("Processing one-time payment")

            # Get package ID from metadata
            package_id = metadata.get("package_id")
            if not package_id:
                logger.error("Package ID not found in payment intent metadata")
                raise ValueError("Package ID is required in metadata")

            # Format metadata for credit addition
            formatted_metadata = {
                "customer_id": customer_id,
                "amount": amount,
                "amount_formatted": amount / 100,
                "amount_received": amount_received,
                "amount_received_formatted": amount_received / 100,
                "currency": currency,
                "payment_method": payment_method,
                "payment_intent_id": payment_intent.id,
            }

            # Add invoice details if available
            if invoice_id:
                invoice = stripe.Invoice.retrieve(invoice_id)
                formatted_metadata.update(
                    {
                        "invoice_id": invoice_id,
                        "invoice_link": invoice.hosted_invoice_url,
                        "invoice_pdf": invoice.invoice_pdf,
                    }
                )

            # Add price ID if available
            if "stripe_price_id" in metadata:
                formatted_metadata["stripe_price_id"] = metadata["stripe_price_id"]

            # Add credits to user account
            await self._add_credit_to_user_account(
                stripe_customer_id=customer_id,
                package_id=package_id,
                payment_intent_id=payment_intent.id,
                metadata=formatted_metadata,
            )

            logger.info(f"Successfully processed payment for {payment_intent.id}")

        except Exception as e:
            logger.error(f"Error processing payment: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to process payment: {str(e)}"
            )

    async def handle_subscription_created(self, subscription: stripe.Subscription):
        try:
            logger.info(
                f"Processing subscription creation for subscription ID: {subscription.id}"
            )
            customer_id = subscription.customer
            user = await self._get_user_by_stripe_customer_id(customer_id)

            # Get package details from metadata
            package_id = subscription.metadata.get("package_id")
            if not package_id:
                raise HTTPException(
                    status_code=400,
                    detail="Package ID not found in subscription metadata",
                )

            package = await self._get_package_details_by_id(package_id)
            # check if user subscription is already exist or not
            subscription_query = (
                select(UserSubscription)
                .where(UserSubscription.platform_subscription_id == subscription.id)
                .where(UserSubscription.user_id == user.id)
            )
            subscription_record = await self.session.execute(subscription_query)
            subscription_details = subscription_record.scalar_one_or_none()

            # Set billing cycle based on package subscription period
            billing_cycle = "monthly"
            credit_allocation_cycle = "monthly"

            if package.subscription_period == "yearly":
                billing_cycle = "yearly"
                # For yearly subscriptions, we allocate credits monthly
                credit_allocation_cycle = "monthly"

            # Calculate next allocation date for yearly subscriptions
            next_credit_allocation_date = None
            if package.subscription_period == "yearly":
                # Get the subscription start date
                subscription_start = datetime.fromtimestamp(
                    subscription.current_period_start, tz=timezone.utc
                )

                # Calculate the next month's date (same day of month)
                next_month = (
                    subscription_start.month + 1 if subscription_start.month < 12 else 1
                )
                next_year = (
                    subscription_start.year
                    if subscription_start.month < 12
                    else subscription_start.year + 1
                )

                # Handle edge cases for months with different numbers of days
                day = subscription_start.day
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
                    elif next_month in [
                        4,
                        6,
                        9,
                        11,
                    ]:  # April, June, September, November
                        day = min(day, 30)  # These months have 30 days

                next_credit_allocation_date = datetime(
                    next_year,
                    next_month,
                    day,
                    subscription_start.hour,
                    subscription_start.minute,
                    subscription_start.second,
                    tzinfo=timezone.utc,
                )

                logger.info(
                    f"Calculated next_credit_allocation_date as {next_credit_allocation_date} based on subscription start date {subscription_start}"
                )

            if subscription_details:
                logger.debug(
                    f"User already has a subscription with ID {subscription.id}. Updating the details."
                )
                subscription_details.status = subscription.status
                subscription_details.current_period_end = datetime.fromtimestamp(
                    subscription.current_period_end, tz=timezone.utc
                )
                subscription_details.cancel_at_period_end = (
                    subscription.cancel_at_period_end
                )
                subscription_details.credits_per_period = package.credits
                subscription_details.billing_cycle = billing_cycle
                subscription_details.credit_allocation_cycle = credit_allocation_cycle

                # Set next allocation date for yearly subscriptions
                if (
                    package.subscription_period == "yearly"
                    and next_credit_allocation_date
                ):
                    subscription_details.next_credit_allocation_date = (
                        next_credit_allocation_date
                    )
                    logger.info(
                        f"Set next_credit_allocation_date to {next_credit_allocation_date} for existing yearly subscription"
                    )

                self.session.add(subscription_details)
                await self.session.commit()
            else:
                logger.debug(
                    f"Creating a new user subscription entry for subscription ID {subscription.id}"
                )

                # Create or update user subscription record
                user_subscription = UserSubscription(
                    user_id=user.id,
                    package_id=UUID(package_id),
                    platform="stripe",
                    platform_subscription_id=subscription.id,
                    status=subscription.status,
                    current_period_start=datetime.fromtimestamp(
                        subscription.current_period_start, tz=timezone.utc
                    ),
                    current_period_end=datetime.fromtimestamp(
                        subscription.current_period_end, tz=timezone.utc
                    ),
                    cancel_at_period_end=subscription.cancel_at_period_end,
                    credits_per_period=package.credits,
                    billing_cycle=billing_cycle,
                    credit_allocation_cycle=credit_allocation_cycle,
                    next_credit_allocation_date=next_credit_allocation_date,
                )
                self.session.add(user_subscription)
                await self.session.commit()

                # Log successful creation
                logger.info(
                    f"Successfully created subscription record for user {user.id} with subscription ID {subscription.id}"
                )

                if next_credit_allocation_date:
                    logger.info(
                        f"Set next_credit_allocation_date to {next_credit_allocation_date} for new yearly subscription"
                    )

            # IMPORTANT: We do NOT add credits here. Credits will be added when the invoice.payment_succeeded event is processed.
            logger.info(
                f"Subscription created successfully. Credits will be added when invoice payment succeeds."
            )

        except Exception as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process subscription creation: {str(e)}",
            )

    async def handle_subscription_updated(self, subscription: stripe.Subscription):
        try:
            # Get the user subscription record
            query = select(UserSubscription).where(
                UserSubscription.platform_subscription_id == subscription.id
            )
            result = await self.session.execute(query)
            user_subscription = result.scalar_one_or_none()

            if not user_subscription:
                logger.debug(
                    f"User subscription not found in database for id {subscription.id}"
                )
                raise HTTPException(
                    status_code=404, detail=f"Subscription not found: {subscription.id}"
                )

            # Update subscription details
            user_subscription.status = subscription.status
            user_subscription.current_period_start = datetime.fromtimestamp(
                subscription.current_period_start, tz=timezone.utc
            )
            user_subscription.current_period_end = datetime.fromtimestamp(
                subscription.current_period_end, tz=timezone.utc
            )
            user_subscription.cancel_at_period_end = subscription.cancel_at_period_end

            await self.session.commit()

        except Exception as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process subscription update: {str(e)}",
            )

    async def handle_subscription_cancelled(self, subscription: stripe.Subscription):
        try:
            # Get the user subscription record
            query = select(UserSubscription).where(
                UserSubscription.platform_subscription_id == subscription.id
            )
            result = await self.session.execute(query)
            user_subscription = result.scalar_one_or_none()

            if not user_subscription:
                raise HTTPException(
                    status_code=404, detail=f"Subscription not found: {subscription.id}"
                )

            # Update subscription status
            user_subscription.status = "cancelled"
            user_subscription.cancel_at_period_end = True

            # Log the cancellation
            metadata = {
                "cancelled_at": datetime.now(timezone.utc).isoformat(),
                "period_end": user_subscription.current_period_end.isoformat(),
                "reason": (
                    subscription.cancellation_details.get("reason")
                    if subscription.cancellation_details
                    else None
                ),
            }

            # Create a transaction record for the cancellation
            transaction = CreditTransaction(
                user_id=str(user_subscription.user_id),
                transaction_type=TransactionType.DEBIT,
                transaction_source=TransactionSource.SUBSCRIPTION_RENEWAL,
                amount=0,  # No credits deducted
                balance_after=0,  # Will be updated by trigger
                description="Subscription cancelled",
                subscription_id=user_subscription.id,
                credit_metadata=metadata,
            )
            self.session.add(transaction)

            await self.session.commit()

        except Exception as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process subscription cancellation: {str(e)}",
            )

    async def handle_subscription_deleted(self, subscription: stripe.Subscription):
        try:
            # Get the user subscription record
            query = select(UserSubscription).where(
                UserSubscription.platform_subscription_id == subscription.id
            )
            result = await self.session.execute(query)
            user_subscription = result.scalar_one_or_none()

            if not user_subscription:
                logger.debug(
                    f"can not find subscription in database for {subscription.id} to delete"
                )
                raise HTTPException(
                    status_code=404, detail=f"Subscription not found: {subscription.id}"
                )

            # Update subscription status
            user_subscription.status = "deleted"
            metadata = {
                "deleted_at": datetime.now(timezone.utc).isoformat(),
                "final_period_end": user_subscription.current_period_end.isoformat(),
            }

            # Create a transaction record for the deletion
            transaction = CreditTransaction(
                user_id=str(user_subscription.user_id),
                transaction_type=TransactionType.DEBIT,
                transaction_source=TransactionSource.SUBSCRIPTION_RENEWAL,
                amount=0,
                balance_after=0,
                description="Subscription deleted",
                subscription_id=user_subscription.id,
                credit_metadata=metadata,
            )
            self.session.add(transaction)

            await self.session.commit()

        except Exception as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process subscription deletion: {str(e)}",
            )

    async def handle_invoice_payment_succeeded(self, invoice: stripe.Invoice):
        try:
            logger.info(
                f"Processing invoice payment succeeded for invoice ID: {invoice.id}"
            )

            subscription_id = invoice.subscription
            if not subscription_id:
                logger.info(
                    f"Invoice {invoice.id} is not for a subscription. Skipping."
                )
                return  # Not a subscription invoice

            # Idempotency check - see if we've already processed this invoice
            invoice_id = invoice.id

            try:
                # Check if we've already processed this invoice by looking for transactions with this invoice ID in metadata
                existing_transaction_query = select(CreditTransaction).where(
                    CreditTransaction.transaction_source
                    == TransactionSource.SUBSCRIPTION_RENEWAL
                )
                existing_transaction_result = await self.session.execute(
                    existing_transaction_query
                )
                existing_transactions = existing_transaction_result.scalars().all()

                # Check each transaction's metadata for the invoice ID
                for transaction in existing_transactions:
                    metadata = transaction.credit_metadata
                    if (
                        metadata
                        and isinstance(metadata, dict)
                        and metadata.get("invoice_id") == invoice_id
                    ):
                        logger.info(
                            f"Transaction for invoice {invoice_id} already exists (ID: {transaction.id}). Skipping credit addition."
                        )
                        return
            except Exception as query_error:
                logger.error(f"Error in idempotency check query: {str(query_error)}")
                # If the query fails, we'll continue with the process
                # This is safer than potentially missing credit additions
                logger.info(
                    "Continuing with credit addition despite idempotency check failure"
                )

            # Get subscription details
            logger.info(
                f"Retrieving subscription details for subscription ID: {subscription_id}"
            )
            subscription = stripe.Subscription.retrieve(subscription_id)

            # Get the user subscription record
            query = select(UserSubscription).where(
                UserSubscription.platform_subscription_id == subscription_id
            )
            result = await self.session.execute(query)
            user_subscription = result.scalar_one_or_none()

            if not user_subscription:
                logger.debug(
                    f"Can not find subscription details for {subscription_id} in database to update"
                )
                raise HTTPException(
                    status_code=404, detail=f"Subscription not found: {subscription_id}"
                )

            # Update subscription period
            logger.info(
                f"Updating subscription period for subscription ID: {subscription_id}"
            )
            user_subscription.current_period_start = datetime.fromtimestamp(
                subscription.current_period_start, tz=timezone.utc
            )
            user_subscription.current_period_end = datetime.fromtimestamp(
                subscription.current_period_end, tz=timezone.utc
            )

            # Add renewal credits
            logger.info(
                f"Adding renewal credits for subscription ID: {subscription_id}"
            )
            package = await self._get_package_details_by_id(
                str(user_subscription.package_id)
            )

            # Calculate expiration and new balance
            current_time = datetime.now(timezone.utc)
            expiration_date = None
            if package.expiration_days:
                expiration_date = current_time + timedelta(days=package.expiration_days)
                logger.info(f"Credits will expire on: {expiration_date}")

            # Get user by subscription user_id
            user_query = select(User).where(User.id == user_subscription.user_id)
            user_result = await self.session.execute(user_query)
            user = user_result.scalar_one_or_none()

            if not user:
                logger.error(
                    f"User not found for subscription user_id: {user_subscription.user_id}"
                )
                raise HTTPException(status_code=404, detail="User not found")

            # Get all active balances for rollover calculation
            active_balances_query = select(UserCreditBalance).where(
                and_(
                    UserCreditBalance.user_id == user_subscription.user_id,
                    UserCreditBalance.is_active == True,
                    UserCreditBalance.remaining_amount > 0,
                    or_(
                        UserCreditBalance.expires_at > current_time,
                        UserCreditBalance.expires_at == None,
                    ),
                )
            )

            active_balances_result = await self.session.execute(active_balances_query)
            active_balances = active_balances_result.scalars().all()

            # Calculate total available credits for rollover
            rollover_amount = sum(
                balance.remaining_amount for balance in active_balances
            )
            logger.info(f"Current rollover amount: {rollover_amount}")

            # Get current balance info
            balance_info = await self._get_or_create_balance(email=user.email)
            current_balance = balance_info["current_balance"]

            # Calculate new balance (current + package credits)
            new_balance = current_balance + package.credits
            logger.info(
                f"Current balance: {current_balance}, New balance after adding credits: {new_balance}"
            )

            # Create credit transaction for the new credits
            logger.info(f"Creating credit transaction for subscription renewal")
            transaction = CreditTransaction(
                user_id=str(user_subscription.user_id),
                transaction_type=TransactionType.CREDIT,
                transaction_source=TransactionSource.SUBSCRIPTION_RENEWAL,
                amount=package.credits,
                balance_after=new_balance,
                description=f"Subscription renewal credits",
                subscription_id=user_subscription.id,
                package_id=str(user_subscription.package_id),
                credit_metadata={
                    "invoice_id": invoice.id,
                    "subscription_id": subscription_id,
                    "period_start": subscription.current_period_start,
                    "period_end": subscription.current_period_end,
                    "rollover_amount": rollover_amount,
                },
            )
            self.session.add(transaction)
            await self.session.flush()
            logger.info(f"Created transaction with ID: {transaction.id}")

            # Create credit balance record for the new credits
            logger.info(f"Creating credit balance record")
            credit_balance = UserCreditBalance(
                user_id=user_subscription.user_id,
                package_id=user_subscription.package_id,
                transaction_id=transaction.id,
                initial_amount=package.credits,
                remaining_amount=package.credits,
                expires_at=expiration_date,
                is_active=True,
            )
            self.session.add(credit_balance)

            # If there are credits to roll over, create a separate transaction and balance record for them
            if rollover_amount > 0:
                logger.info(
                    f"Creating rollover credit balance record for {rollover_amount} credits"
                )

                # Create a separate transaction for rollover credits
                rollover_transaction = CreditTransaction(
                    user_id=str(user_subscription.user_id),
                    transaction_type=TransactionType.CREDIT,
                    transaction_source=TransactionSource.SUBSCRIPTION_RENEWAL,
                    amount=rollover_amount,
                    balance_after=new_balance,  # Same balance after as the main transaction
                    description=f"Rollover credits from subscription renewal",
                    subscription_id=user_subscription.id,
                    package_id=str(user_subscription.package_id),
                    credit_metadata={
                        "invoice_id": invoice.id,
                        "subscription_id": subscription_id,
                        "period_start": subscription.current_period_start,
                        "period_end": subscription.current_period_end,
                        "is_rollover": True,
                        "parent_transaction_id": str(transaction.id),
                    },
                )
                self.session.add(rollover_transaction)
                await self.session.flush()
                logger.info(
                    f"Created rollover transaction with ID: {rollover_transaction.id}"
                )

                # Only mark old balances as inactive if they have a remaining amount
                balances_to_mark_inactive = [
                    balance
                    for balance in active_balances
                    if balance.remaining_amount > 0
                ]

                if balances_to_mark_inactive:
                    # Create balance record for rollover credits with the new transaction ID
                    rollover_balance = UserCreditBalance(
                        user_id=user_subscription.user_id,
                        package_id=user_subscription.package_id,
                        transaction_id=rollover_transaction.id,  # Use the rollover transaction ID
                        initial_amount=rollover_amount,
                        remaining_amount=rollover_amount,
                        expires_at=expiration_date,  # Use the same expiration as the new credits
                        is_active=True,
                    )
                    self.session.add(rollover_balance)

                    # Mark the old balances as inactive so they won't be rolled over again
                    for balance in balances_to_mark_inactive:
                        balance.is_active = False
                        balance.consumed_at = current_time
                        self.session.add(balance)

                    logger.info(
                        f"Marked {len(balances_to_mark_inactive)} old balances as inactive after rollover"
                    )
                else:
                    logger.info(
                        "No active balances with remaining credits to mark as inactive"
                    )

            await self.session.commit()
            logger.info(
                f"Successfully added {package.credits} credits for subscription renewal with {rollover_amount} rollover credits"
            )

        except Exception as e:
            logger.error(f"Error processing invoice payment: {str(e)}")
            await self.session.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process subscription renewal: {str(e)}",
            )

    async def get_stripe_customer_payment_methods(self, email: str):
        user = await self._get_user_by_email(email)
        payment_methods = stripe.PaymentMethod.list(
            customer=user.stripe_customer_id, type="card"
        )

        return {
            "payment_methods": payment_methods.data,
            "customer_id": user.stripe_customer_id,
        }

    async def get_current_user_active_subscription(self, email: str):
        user = await self._get_user_by_email(email)

        try:
            if user:
                subscription_query = (
                    select(UserSubscription)
                    .where(UserSubscription.user_id == user.id)
                    .where(UserSubscription.status == "active")
                    .order_by(UserSubscription.updated_at.desc())
                )
                subscription_record = await self.session.execute(subscription_query)
                user_subscription = subscription_record.scalar_one_or_none()

                if not user_subscription:
                    raise HTTPException(detail="No active subscription found for user")

                subscription_id = user_subscription.platform_subscription_id
                customer_id = user.stripe_customer_id

                # Retrieve subscription
                subscription = stripe.Subscription.retrieve(
                    user_subscription.platform_subscription_id,
                    expand=["default_payment_method", "customer", "latest_invoice"],
                )

                # Corrected line: Access 'items' using dictionary-style
                subscription_items = list(subscription["items"])
                if not subscription_items:
                    raise HTTPException(detail="No items found in subscription")

                # Rest of the code remains the same...
                # Fetch upcoming invoice
                try:
                    upcoming_invoice = stripe.Invoice.upcoming(
                        subscription=subscription_id, customer=customer_id
                    )
                except stripe.error.StripeError as e:
                    logger.warning(f"Could not fetch upcoming invoice: {str(e)}")
                    upcoming_invoice = None

                # Convert timestamps to readable dates
                start_date = datetime.fromtimestamp(subscription.start_date).strftime(
                    "%Y-%m-%d"
                )
                current_period_end = datetime.fromtimestamp(
                    subscription.current_period_end
                ).strftime("%Y-%m-%d")
                canceled_at = None
                if subscription.canceled_at:
                    canceled_at = datetime.fromtimestamp(
                        subscription.canceled_at
                    ).strftime("%Y-%m-%d")

                # Get payment method details
                payment_method = None
                if subscription.default_payment_method:
                    payment_method = {
                        "type": subscription.default_payment_method.type,
                        "last4": subscription.default_payment_method.card.last4,
                        "brand": subscription.default_payment_method.card.brand,
                        "exp_month": subscription.default_payment_method.card.exp_month,
                        "exp_year": subscription.default_payment_method.card.exp_year,
                    }

                # Compile subscription details
                subscription_details = {
                    "subscription_id": subscription.id,
                    "status": subscription.status,
                    "start_date": start_date,
                    "next_invoice_date": current_period_end,
                    "price": {
                        "amount": subscription_items[0].price.unit_amount / 100,
                        "currency": subscription_items[0].price.currency,
                        "interval": subscription_items[0].price.recurring.interval,
                        "interval_count": subscription_items[
                            0
                        ].price.recurring.interval_count,
                    },
                    "customer": {
                        "id": subscription.customer.id,
                        "name": subscription.customer.name,
                        "email": subscription.customer.email,
                    },
                    "payment_method": payment_method,
                    "cancellation": {
                        "canceled_at": canceled_at,
                        "cancel_at_period_end": subscription.cancel_at_period_end,
                        "cancellation_reason": (
                            subscription.cancellation_details.reason
                            if hasattr(subscription, "cancellation_details")
                            else None
                        ),
                        "cancellation_comment": (
                            subscription.cancellation_details.comment
                            if hasattr(subscription, "cancellation_details")
                            else None
                        ),
                    },
                    "current_period": {
                        "start": datetime.fromtimestamp(
                            subscription.current_period_start
                        ).strftime("%Y-%m-%d"),
                        "end": datetime.fromtimestamp(
                            subscription.current_period_end
                        ).strftime("%Y-%m-%d"),
                    },
                    "metadata": subscription.metadata,
                }

                if upcoming_invoice:
                    subscription_details["upcoming_invoice"] = {
                        "amount_due": upcoming_invoice.amount_due / 100,
                        "currency": upcoming_invoice.currency,
                        "due_date": datetime.fromtimestamp(
                            upcoming_invoice.created
                        ).strftime("%Y-%m-%d"),
                        "status": upcoming_invoice.status,
                        "hosted_invoice_url": getattr(
                            upcoming_invoice, "hosted_invoice_url", None
                        ),
                    }
                else:
                    subscription_details["upcoming_invoice"] = None

                return subscription_details

            raise HTTPException(detail="User not found for given email")

        except stripe.error.StripeError as e:
            logger.error(f"Error fetching active subscription: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to fetch active subscription: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Error fetching active subscription: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to fetch active subscription: {str(e)}"
            )

    async def process_yearly_subscription_monthly_credits(self, user_email: str = None):
        """
        Process monthly credit allocation for yearly subscriptions.
        This method should be called by a cronjob once a month.

        If user_email is provided, process only for that user, otherwise process for all users with yearly subscriptions.
        """
        try:
            logger.info("Starting monthly credit allocation for yearly subscriptions")

            # Build the query to find active yearly subscriptions
            if user_email:
                logger.info(f"Processing for specific user: {user_email}")
                # Get user by email
                user_query = select(User).where(User.email == user_email)
                user_result = await self.session.execute(user_query)
                user = user_result.scalar_one_or_none()

                if not user:
                    logger.error(f"User not found with email: {user_email}")
                    raise HTTPException(
                        status_code=404,
                        detail=f"User not found with email: {user_email}",
                    )

                # Get active yearly subscriptions for this user
                subscriptions_query = select(UserSubscription).where(
                    and_(
                        UserSubscription.user_id == user.id,
                        UserSubscription.status == "active",
                        UserSubscription.payment_interval == "year",
                    )
                )
            else:
                logger.info("Processing for all users with yearly subscriptions")
                # Get all active yearly subscriptions
                subscriptions_query = (
                    select(UserSubscription)
                    .join(User, UserSubscription.user_id == User.id)
                    .where(
                        and_(
                            UserSubscription.status == "active",
                            UserSubscription.payment_interval == "year",
                        )
                    )
                )

            subscriptions_result = await self.session.execute(subscriptions_query)
            subscriptions = subscriptions_result.scalars().all()

            logger.info(f"Found {len(subscriptions)} active yearly subscriptions")

            # Process each subscription
            for subscription in subscriptions:
                await self._process_monthly_credits_for_subscription(subscription)

            return {
                "success": True,
                "message": f"Processed {len(subscriptions)} yearly subscriptions",
            }

        except Exception as e:
            logger.error(
                f"Error processing yearly subscription monthly credits: {str(e)}"
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process yearly subscription monthly credits: {str(e)}",
            )

    async def _process_monthly_credits_for_subscription(
        self, subscription: UserSubscription
    ):
        """
        Process monthly credit allocation for a single yearly subscription.
        """
        try:
            # Get user
            user_query = select(User).where(User.id == subscription.user_id)
            user_result = await self.session.execute(user_query)
            user = user_result.scalar_one_or_none()

            if not user:
                logger.error(f"User not found for subscription ID: {subscription.id}")
                return

            logger.info(
                f"Processing monthly credits for user: {user.email}, subscription ID: {subscription.id}"
            )

            # Get package details
            package = await self._get_package_details_by_id(
                str(subscription.package_id)
            )

            # Check when the last credit allocation was made
            last_transaction_query = (
                select(CreditTransaction)
                .where(
                    and_(
                        CreditTransaction.user_id == str(subscription.user_id),
                        CreditTransaction.transaction_source
                        == TransactionSource.SUBSCRIPTION_RENEWAL,
                        CreditTransaction.subscription_id == subscription.id,
                    )
                )
                .order_by(CreditTransaction.created_at.desc())
            )

            last_transaction_result = await self.session.execute(last_transaction_query)
            last_transaction = last_transaction_result.scalar_one_or_none()

            current_time = datetime.now(timezone.utc)

            # If no transaction found or last transaction was more than 25 days ago
            if (
                not last_transaction
                or (current_time - last_transaction.created_at).days >= 25
            ):
                # Check for idempotency - make sure we haven't already added credits this month
                # Create a unique identifier for this month's allocation
                current_month_year = f"{current_time.year}-{current_time.month}"

                # Check if we already processed this month
                existing_monthly_query = select(CreditTransaction).where(
                    and_(
                        CreditTransaction.user_id == str(subscription.user_id),
                        CreditTransaction.transaction_source
                        == TransactionSource.SUBSCRIPTION_RENEWAL,
                        CreditTransaction.subscription_id == subscription.id,
                    )
                )

                existing_monthly_result = await self.session.execute(
                    existing_monthly_query
                )
                all_monthly_transactions = existing_monthly_result.scalars().all()

                already_processed = False
                for transaction in all_monthly_transactions:
                    metadata = transaction.credit_metadata
                    if (
                        metadata
                        and isinstance(metadata, dict)
                        and metadata.get("monthly_allocation") == True
                        and metadata.get("allocation_month") == current_month_year
                    ):
                        logger.info(
                            f"Monthly allocation for {current_month_year} already processed for subscription {subscription.id}"
                        )
                        already_processed = True
                        break

                if already_processed:
                    return

                # Get current active balances for rollover
                active_balances_query = select(UserCreditBalance).where(
                    and_(
                        UserCreditBalance.user_id == subscription.user_id,
                        UserCreditBalance.is_active == True,
                        UserCreditBalance.remaining_amount > 0,
                        or_(
                            UserCreditBalance.expires_at > current_time,
                            UserCreditBalance.expires_at == None,
                        ),
                    )
                )

                active_balances_result = await self.session.execute(
                    active_balances_query
                )
                active_balances = active_balances_result.scalars().all()

                # Calculate total available credits for rollover
                rollover_amount = sum(
                    balance.remaining_amount for balance in active_balances
                )
                logger.info(f"Current rollover amount: {rollover_amount}")

                # Get current balance
                balance_info = await self._get_or_create_balance(email=user.email)
                current_balance = balance_info["current_balance"]

                # Calculate monthly credit amount (yearly credits / 12)
                monthly_credits = subscription.credits_per_period / 12
                new_balance = current_balance + monthly_credits

                # Calculate expiration date
                expiration_date = None
                if package.expiration_days:
                    expiration_date = current_time + timedelta(
                        days=package.expiration_days
                    )

                # Create transaction record for monthly credits
                transaction = CreditTransaction(
                    user_id=str(subscription.user_id),
                    transaction_type=TransactionType.CREDIT,
                    transaction_source=TransactionSource.SUBSCRIPTION_RENEWAL,
                    amount=monthly_credits,
                    balance_after=new_balance,
                    description=f"Monthly credit allocation for yearly subscription",
                    subscription_id=subscription.id,
                    package_id=str(subscription.package_id),
                    credit_metadata={
                        "allocation_month": current_month_year,
                        "rollover_amount": rollover_amount,
                        "yearly_subscription_id": subscription.platform_subscription_id,
                        "monthly_allocation": True,
                    },
                )
                self.session.add(transaction)
                await self.session.flush()

                # Create credit balance record for the new monthly credits
                credit_balance = UserCreditBalance(
                    user_id=subscription.user_id,
                    package_id=subscription.package_id,
                    transaction_id=transaction.id,
                    initial_amount=monthly_credits,
                    remaining_amount=monthly_credits,
                    expires_at=expiration_date,
                    is_active=True,
                )
                self.session.add(credit_balance)

                # If there are credits to roll over, create a separate transaction and balance record for them
                if rollover_amount > 0:
                    logger.info(
                        f"Creating rollover credit balance record for {rollover_amount} credits"
                    )

                    # Create a separate transaction for rollover credits
                    rollover_transaction = CreditTransaction(
                        user_id=str(subscription.user_id),
                        transaction_type=TransactionType.CREDIT,
                        transaction_source=TransactionSource.SUBSCRIPTION_RENEWAL,
                        amount=rollover_amount,
                        balance_after=new_balance,  # Same balance after as the main transaction
                        description=f"Rollover credits from monthly allocation",
                        subscription_id=subscription.id,
                        package_id=str(subscription.package_id),
                        credit_metadata={
                            "allocation_month": current_month_year,
                            "is_rollover": True,
                            "monthly_allocation": True,
                            "yearly_subscription_id": subscription.platform_subscription_id,
                            "parent_transaction_id": str(transaction.id),
                        },
                    )
                    self.session.add(rollover_transaction)
                    await self.session.flush()
                    logger.info(
                        f"Created rollover transaction with ID: {rollover_transaction.id}"
                    )

                    # Only mark old balances as inactive if they have a remaining amount
                    balances_to_mark_inactive = [
                        balance
                        for balance in active_balances
                        if balance.remaining_amount > 0
                    ]

                    if balances_to_mark_inactive:
                        # Create balance record for rollover credits with the new transaction ID
                        rollover_balance = UserCreditBalance(
                            user_id=subscription.user_id,
                            package_id=subscription.package_id,
                            transaction_id=rollover_transaction.id,  # Use the rollover transaction ID
                            initial_amount=rollover_amount,
                            remaining_amount=rollover_amount,
                            expires_at=expiration_date,  # Use the same expiration as the new credits
                            is_active=True,
                        )
                        self.session.add(rollover_balance)

                        # Mark the old balances as inactive so they won't be rolled over again
                        for balance in balances_to_mark_inactive:
                            balance.is_active = False
                            balance.consumed_at = current_time
                            self.session.add(balance)

                        logger.info(
                            f"Marked {len(balances_to_mark_inactive)} old balances as inactive after rollover"
                        )
                    else:
                        logger.info(
                            "No active balances with remaining credits to mark as inactive"
                        )

                await self.session.commit()
                logger.info(
                    f"Successfully added {monthly_credits} monthly credits for yearly subscription {subscription.id} with {rollover_amount} rollover credits"
                )
            else:
                days_since_last = (current_time - last_transaction.created_at).days
                logger.info(
                    f"Skipping credit allocation - last transaction was only {days_since_last} days ago"
                )

        except Exception as e:
            logger.error(
                f"Error processing monthly credits for subscription {subscription.id}: {str(e)}"
            )
            await self.session.rollback()
            # Don't raise the exception, just log it and continue with other subscriptions
