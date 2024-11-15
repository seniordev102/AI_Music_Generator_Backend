from typing import Optional

import stripe
from fastapi import Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.credit_management.service import CreditManagementService
from app.api.credit_packages.service import CreditPackageService
from app.auth.auth_handler import AuthHandler
from app.auth.token_handler import JWTTokenHandler
from app.config import settings
from app.database import db_session
from app.logger.logger import logger
from app.models import TransactionSource, User


class IAHStripeService:
    def __init__(self, session: AsyncSession = Depends(db_session)) -> str:
        self.session = session
        self.settings = settings
        stripe.api_key = settings.STRIPE_SECRET_KEY
        stripe.api_version = settings.STRIPE_API_VERSION

    def get_stripe_publisher_key(self) -> str:
        return self.settings.STRIPE_PUBLIC_KEY

    async def get_active_stripe_products(self):
        active_products = stripe.Product.list(active=True)

        product_list_with_price = []

        for product in active_products:
            if product.default_price is not None:
                price = stripe.Price.retrieve(id=product.default_price)
                product_list_with_price.append({"product": product, "price": price})
        return product_list_with_price

    async def get_or_create_stripe_customer_id(self, email: str):
        # get user account based on user email address
        user_record = await self.session.execute(
            select(User).where(User.email == email)
        )
        user: User = user_record.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        # check user has customer id
        stripe_customer_id = user.stripe_customer_id

        if stripe_customer_id is None:
            logger.debug("stripe customer id not found creating stripe customer")
            # create stripe customer and return customer id
            customer = stripe.Customer.create(name=user.name, email=email)

            return customer.id
        else:
            logger.debug("stripe customer already found returning customer id")
            return user.stripe_customer_id

    async def list_all_stripe_coupons(self):
        # return all stripe coupons max limit 100
        return stripe.Coupon.list()

    async def get_stripe_coupon_by_id(self, coupon_id: str):
        # return all stripe coupons max limit 100
        return stripe.Coupon.retrieve(id=coupon_id)

    async def get_stripe_coupon_by_name(self, coupon_name: str):
        matching_coupons = []

        # Use auto-pagination to iterate through all coupons
        for coupon in stripe.Coupon.list().auto_paging_iter():
            if coupon.name == coupon_name:
                matching_coupons.append(coupon)

        if len(matching_coupons) > 0:
            return matching_coupons[0]
        else:
            return None

    async def create_stripe_subscription(
        self, customer_id: str, price_id: str, coupon_id: str
    ):

        subscription_params = {
            "customer": customer_id,
            "items": [
                {
                    "price": price_id,
                }
            ],
            "payment_behavior": "default_incomplete",
            "payment_settings": {"save_default_payment_method": "on_subscription"},
            "expand": ["latest_invoice.payment_intent"],
        }

        if coupon_id:
            subscription_params["discounts"] = [{"coupon": coupon_id}]

        subscription = stripe.Subscription.create(**subscription_params)

        # Get the client secret for the payment
        payment_intent = (
            subscription["latest_invoice"].get("payment_intent")
            if subscription.get("latest_invoice")
            else None
        )

        return {
            "subscription_id": subscription.id,
            "client_secret": (
                payment_intent["client_secret"] if payment_intent else None
            ),
        }

    async def create_iah_affiliate_user(self, name: str, email: str, password: str):

        email_lower_case = email.lower()
        user_record = await self.session.execute(
            select(User).where(User.email == email_lower_case)
        )
        user = user_record.scalar_one_or_none()

        if user:
            raise HTTPException(
                status_code=400, detail="User with this email already exists"
            )

        #  create new user and save the user details to the database
        stripe_customer = stripe.Customer.create(
            email=email, name=name, metadata={"subscription_plan": "IAH Affiliate"}
        )

        # create stripe setup intent
        setup_intent = stripe.SetupIntent.create(
            customer=stripe_customer.id,
            payment_method_types=["card"],
            metadata={"user_email": email},
        )

        # hashed the password
        auth_handler = AuthHandler()
        hashed_password = auth_handler.hash_password(password)

        # create user object for saving
        user = User(
            name=name,
            email=email.lower(),
            hashed_password=hashed_password,
            stripe_customer_id=stripe_customer.id,
            monthly_limit_ask_iah_queries=10000,
            monthly_limit_craft_my_sonics=10000,
            monthly_limit_sonic_supplement_shuffles=10000,
            monthly_limit_super_sonic_shuffles=10000,
            monthly_limit_ask_iah_playlist_generation=10000,
            monthly_limit_ask_iah_image_generation=10000,
            invite_code=None,
        )

        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)

        return {
            "customerId": stripe_customer.id,
            "clientSecret": setup_intent.client_secret,
            "setupIntentId": setup_intent.id,
        }

    async def create_iah_affiliate_subscription(
        self,
        customer_id: str,
        payment_method_id: str,
        price_id: str,
        coupon_code: Optional[str],
    ):

        # Attach payment method to customer
        payment_method = stripe.PaymentMethod.attach(
            payment_method_id,
            customer=customer_id,
        )

        # Set as default payment method
        stripe.Customer.modify(
            customer_id,
            invoice_settings={
                "default_payment_method": payment_method.id,
            },
        )

        # Create subscription
        subscription_data = {
            "customer": customer_id,
            "items": [{"price": price_id}],
            "default_payment_method": payment_method.id,
            "expand": ["latest_invoice.payment_intent"],
        }

        # Add coupon if provided

        subscription = stripe.Subscription.create(**subscription_data)

        # Get the invoice and payment intent
        invoice = subscription.latest_invoice
        payment_intent = invoice.payment_intent

        # Confirm the PaymentIntent
        if payment_intent.status == "requires_confirmation":
            payment_intent = stripe.PaymentIntent.confirm(
                payment_intent.id,
                payment_method=payment_method.id,
            )

        user_record = await self.session.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user: User = user_record.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user.subscription_id = subscription.id
        user.subscription_status = subscription.status
        await self.session.commit()

        return {
            "subscriptionId": subscription.id,
            "magicLink": "https://google.com",
            "requiresAction": payment_intent.status == "requires_action",
            "paymentIntentClientSecret": (
                payment_intent.client_secret
                if payment_intent.status == "requires_action"
                else None
            ),
        }

    async def validate_stripe_user_account(self, email: str):

        email_lower_case = email.lower()
        user_record = await self.session.execute(
            select(User).where(User.email == email_lower_case)
        )
        user: User = user_record.scalar_one_or_none()

        is_account_creation_required = True

        if user is not None:
            is_account_creation_required = False

        stripe_customer = self._get_stripe_customer_details(email=email)

        can_proceed = True

        if user == None and stripe_customer == None:
            can_proceed = False

        return {
            "is_account_creation_required": is_account_creation_required,
            "user": user,
            "stripe_customer": stripe_customer,
            "valid_request": can_proceed,
        }

    async def authenticate_affiliate_user(self, email: str, password: str):

        email_lower_case = email.lower()
        user_record = await self.session.execute(
            select(User).where(User.email == email_lower_case)
        )
        user: User = user_record.scalar_one_or_none()

        token_handler = JWTTokenHandler()
        auth_handler = AuthHandler()

        # fetch the stripe customer details using email
        stripe_customer = self._get_stripe_customer_details(email=email)

        subscriptions = stripe.Subscription.list(customer=stripe_customer.id, limit=1)

        if subscriptions["data"]:
            latest_subscription = subscriptions["data"][
                0
            ]  # Assuming you want the latest subscription
            subscription_id = latest_subscription["id"]

            # Extract subscription item details
            subscription_item = latest_subscription["items"]["data"][
                0
            ]  # First item in the subscription
            item_id = subscription_item["id"]
            price_id = subscription_item["price"]["id"]
            product_id = subscription_item["price"]["product"]
            lookup_key = subscription_item["price"]["lookup_key"]

            subscription_item = latest_subscription["items"]["data"][
                0
            ]  # First item in the subscription
            item_id = subscription_item["id"]  # subscription_item_id
            interval = subscription_item["price"]["recurring"]["interval"]

            if lookup_key == None:
                key = "free"
            else:
                key = lookup_key

            latest_invoice_id = latest_subscription["latest_invoice"]
            if latest_invoice_id:
                latest_invoice = stripe.Invoice.retrieve(str(latest_invoice_id))
                payment_status = latest_invoice.get("status")

            monthly_limit_ask_iah_queries = 10000
            monthly_limit_craft_my_sonics = 10000
            monthly_limit_sonic_supplement_shuffles = 10000
            monthly_limit_super_sonic_shuffles = 10000
            monthly_limit_ask_iah_playlist_generation = 10000
            monthly_limit_ask_iah_image_generation = 10000

            if interval == "year":

                monthly_limit_ask_iah_queries = 10000 * 12
                monthly_limit_craft_my_sonics = 10000 * 12
                monthly_limit_sonic_supplement_shuffles = 10000 * 12
                monthly_limit_super_sonic_shuffles = 10000 * 12
                monthly_limit_ask_iah_playlist_generation = 10000 * 12
                monthly_limit_ask_iah_image_generation = 10000 * 12

            # hash the password
            hashed_password = auth_handler.hash_password(password)

            if user is None:
                # create the new user
                user = User(
                    name=stripe_customer.name,
                    hashed_password=hashed_password,
                    email=email.lower(),
                    stripe_customer_id=stripe_customer.id,
                    stripe_price_id=price_id,
                    stripe_product_id=product_id,
                    payment_interval=interval,
                    subscription_id=subscription_id,
                    subscription_item_id=item_id,
                    active_subscription_id=price_id,
                    subscription_plan=key,
                    subscription_status=payment_status,
                    monthly_limit_ask_iah_queries=monthly_limit_ask_iah_queries,
                    monthly_limit_craft_my_sonics=monthly_limit_craft_my_sonics,
                    monthly_limit_sonic_supplement_shuffles=monthly_limit_sonic_supplement_shuffles,
                    monthly_limit_super_sonic_shuffles=monthly_limit_super_sonic_shuffles,
                    monthly_limit_ask_iah_playlist_generation=monthly_limit_ask_iah_playlist_generation,
                    monthly_limit_ask_iah_image_generation=monthly_limit_ask_iah_image_generation,
                )

                # save the user and authenticate
                self.session.add(user)
                await self.session.commit()
                await self.session.refresh(user)

                access_token = token_handler.create_access_token(
                    data={"sub": user.email}
                )
                refresh_token = token_handler.create_refresh_token(
                    data={"sub": user.email}
                )

                return {
                    "user": user,
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "bearer",
                }

            else:

                # update user details
                user.stripe_customer_id = stripe_customer.id
                user.stripe_price_id = price_id
                user.stripe_product_id = product_id
                user.payment_interval = interval
                user.subscription_id = subscription_id
                user.subscription_item_id = item_id
                user.active_subscription_id = price_id
                user.subscription_plan = key
                user.subscription_status = payment_status

                await self.session.commit()

                encoded_password = password.encode("utf-8")

                # verify the password and and send the user details
                is_valid_password = auth_handler.verify_password(
                    encoded_password, user.hashed_password
                )

                if not is_valid_password:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Incorrect email or password",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                access_token = token_handler.create_access_token(
                    data={"sub": user.email}
                )
                refresh_token = token_handler.create_refresh_token(
                    data={"sub": user.email}
                )

                return {
                    "user": user,
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "bearer",
                }

        else:

            monthly_limit_ask_iah_queries = 10000
            monthly_limit_craft_my_sonics = 10000
            monthly_limit_sonic_supplement_shuffles = 10000
            monthly_limit_super_sonic_shuffles = 10000
            monthly_limit_ask_iah_playlist_generation = 10000
            monthly_limit_ask_iah_image_generation = 10000

            if user is None:
                # create the new user
                user = User(
                    name=stripe_customer.name,
                    hashed_password=hashed_password,
                    email=email.lower(),
                    stripe_customer_id=stripe_customer.id,
                    subscription_plan="free",
                    monthly_limit_ask_iah_queries=monthly_limit_ask_iah_queries,
                    monthly_limit_craft_my_sonics=monthly_limit_craft_my_sonics,
                    monthly_limit_sonic_supplement_shuffles=monthly_limit_sonic_supplement_shuffles,
                    monthly_limit_super_sonic_shuffles=monthly_limit_super_sonic_shuffles,
                    monthly_limit_ask_iah_playlist_generation=monthly_limit_ask_iah_playlist_generation,
                    monthly_limit_ask_iah_image_generation=monthly_limit_ask_iah_image_generation,
                )

                # save the user and authenticate
                self.session.add(user)
                await self.session.commit()
                await self.session.refresh(user)

                access_token = token_handler.create_access_token(
                    data={"sub": user.email}
                )
                refresh_token = token_handler.create_refresh_token(
                    data={"sub": user.email}
                )

                return {
                    "user": user,
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "bearer",
                }

            else:

                # update user details
                user.stripe_customer_id = stripe_customer.id
                user.stripe_price_id = price_id
                user.stripe_product_id = product_id
                user.payment_interval = interval
                user.subscription_id = subscription_id
                user.subscription_item_id = item_id
                user.active_subscription_id = price_id
                user.subscription_plan = key
                user.subscription_status = payment_status

                await self.session.commit()

                encoded_password = password.encode("utf-8")

                # verify the password and and send the user details
                is_valid_password = auth_handler.verify_password(
                    encoded_password, str(user.hashed_password)
                )
                if not is_valid_password:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Incorrect email or password",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                access_token = token_handler.create_access_token(
                    data={"sub": user.email}
                )
                refresh_token = token_handler.create_refresh_token(
                    data={"sub": user.email}
                )

                return {
                    "user": user,
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "bearer",
                }

    def _get_stripe_customer_details(self, email: str):
        customers = stripe.Customer.list(email=email, limit=1)
        latest_stripe_customer_details = customers.data

        if len(latest_stripe_customer_details) > 0:
            return latest_stripe_customer_details[0]
        else:
            return None

    async def get_user_subscription_status(self, email: str):
        email_lower_case = email.lower()
        user_record = await self.session.execute(
            select(User).where(User.email == email_lower_case)
        )
        user: User = user_record.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        stripe_customer_id = user.stripe_customer_id

        if stripe_customer_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stripe user customer id not found",
            )

        subscriptions = stripe.Subscription.list(customer=stripe_customer_id)

        if len(subscriptions["data"]) > 0:
            subscription = subscriptions["data"][len(subscriptions["data"]) - 1]

            subscription_id = subscription["id"]
            subscription_status = subscription["status"]
            next_invoice_date = subscription["current_period_end"]
            items = subscription["items"]["data"]

            latest_item = items[-1]
            interval = latest_item["plan"]["interval"]
            amount_cents = latest_item["plan"]["amount"]
            amount_dollars = amount_cents / 100

            cancel_at = subscription["cancel_at"]
            cancel_at_period_end = subscription["cancel_at_period_end"]

            price_id = latest_item["price"]["id"]
            product_id = latest_item["price"]["product"]

            product_name = f"IAH Premium {'Monthly' if interval == 'month' else 'Yearly' if interval == 'year' else ''}"

            return {
                "id": subscription_id,
                "name": product_name,
                "interval": interval,
                "amount_in_dollar": amount_dollars,
                "subscription_status": subscription_status,
                "next_billing_date": next_invoice_date,
                "cancel_at_period_end": cancel_at_period_end,
                "cancel_at": cancel_at,
                "price_id": price_id,
                "product_id": product_id,
            }

        else:
            return None

    async def get_stripe_customer_payment_methods(self, email: str):
        email_lower_case = email.lower()
        user_record = await self.session.execute(
            select(User).where(User.email == email_lower_case)
        )
        user: User = user_record.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        stripe_customer_id = user.stripe_customer_id

        if stripe_customer_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stripe user customer id not found",
            )

        payment_methods = stripe.PaymentMethod.list(
            customer=stripe_customer_id, type="card"
        )

        if len(payment_methods) > 0:
            return payment_methods["data"]
        else:
            return []

    async def detach_payment_method_from_customer(
        self, email: str, payment_method_id: str
    ):
        email_lower_case = email.lower()
        user_record = await self.session.execute(
            select(User).where(User.email == email_lower_case)
        )
        user: User = user_record.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        stripe_customer_id = user.stripe_customer_id

        if stripe_customer_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stripe user customer id not found",
            )

        detach_response = stripe.PaymentMethod.detach(payment_method_id)

        return detach_response

    async def cancel_user_subscriptions(self, email: str, subscription_id: str):
        email_lower_case = email.lower()
        user_record = await self.session.execute(
            select(User).where(User.email == email_lower_case)
        )
        user: User = user_record.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        stripe_customer_id = user.stripe_customer_id

        if stripe_customer_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stripe user customer id not found",
            )

        subscription = stripe.Subscription.modify(
            subscription_id, cancel_at_period_end=True
        )

        return subscription

    async def resume_user_subscriptions(self, email: str, subscription_id: str):
        email_lower_case = email.lower()
        user_record = await self.session.execute(
            select(User).where(User.email == email_lower_case)
        )
        user: User = user_record.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        stripe_customer_id = user.stripe_customer_id

        if stripe_customer_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stripe user customer id not found",
            )

        subscription = stripe.Subscription.modify(
            id=subscription_id,
            cancel_at_period_end=False,
        )

        return subscription

    async def update_user_subscription(
        self, email: str, subscription_id: str, new_price_id: str, coupon_id: str
    ):
        email_lower_case = email.lower()
        user_record = await self.session.execute(
            select(User).where(User.email == email_lower_case)
        )
        user: User = user_record.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        stripe_customer_id = user.stripe_customer_id

        if stripe_customer_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stripe user customer id not found",
            )

        # get current subscription details
        subscription = stripe.Subscription.retrieve(id=subscription_id)

        if subscription:
            items = subscription["items"]["data"]
            latest_item = items[-1]
            price_id = latest_item["price"]["id"]
            subscription_item_id = latest_item["id"]

            if price_id == new_price_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The subscription plan you selected is the same as your current plan. Please choose a different plan to upgrade or downgrade.",
                )

            # Create parameters for subscription update
            subscription_params = {
                "items": [
                    {
                        "id": subscription_item_id,
                        "price": new_price_id,
                    }
                ],
                "proration_behavior": "create_prorations",
                "payment_behavior": "default_incomplete",
                "payment_settings": {"save_default_payment_method": "on_subscription"},
                "expand": ["latest_invoice.payment_intent"],
            }

            # Add the coupon if provided
            if coupon_id:
                subscription_params["discounts"] = [{"coupon": coupon_id}]

            # Execute the subscription update
            updated_subscription = stripe.Subscription.modify(
                subscription_id, **subscription_params
            )

            # Get the client secret for the payment
            payment_intent = (
                updated_subscription["latest_invoice"].get("payment_intent")
                if updated_subscription.get("latest_invoice")
                else None
            )

            return {
                "subscription_id": updated_subscription["id"],
                "client_secret": (
                    payment_intent["client_secret"] if payment_intent else None
                ),
            }

        return False

    async def _get_user_by_stripe_customer_id(self, customer_id: str) -> User:
        """Get user by Stripe customer ID"""
        query = select(User).where(User.stripe_customer_id == customer_id)
        result = await self.session.execute(query)
        user = result.scalars().first()

        if not user:
            raise HTTPException(
                status_code=404,
                detail=f"User with Stripe customer ID {customer_id} not found",
            )

        return user

    async def handle_subscription_renewal(
        self,
        invoice: dict,
        credit_service: CreditManagementService,
        package_service: CreditPackageService,
    ):
        """Handle subscription renewal invoice payment"""
        try:
            # Get subscription and customer details
            subscription_id = invoice.get("subscription")
            customer_id = invoice.get("customer")

            # Get the subscription from Stripe to get the price ID
            subscription = stripe.Subscription.retrieve(subscription_id)
            price_id = subscription.items.data[0].price.id

            # Get the credit package associated with this price ID
            credit_package = await package_service.get_package_by_platform_id(
                platform="stripe", product_id=price_id
            )

            # Get user by Stripe customer ID
            user = await self._get_user_by_stripe_customer_id(customer_id)

            # Add credits for the renewal
            await credit_service.add_credits(
                user_email=user.email,
                amount=credit_package["credits"],
                source=TransactionSource.SUBSCRIPTION_RENEWAL,
                platform_transaction_id=invoice.get("payment_intent"),
                subscription_id=subscription_id,
                package_id=credit_package["id"],
                metadata={
                    "stripe_invoice_id": invoice.get("id"),
                    "stripe_customer_id": customer_id,
                    "subscription_id": subscription_id,
                    "period_start": subscription.current_period_start,
                    "period_end": subscription.current_period_end,
                },
            )

        except Exception as e:
            print(f"Error processing subscription renewal: {str(e)}")
            # You might want to notify admin or retry later
            raise

    async def handle_one_time_purchase(
        self,
        checkout_session: dict,
        credit_service: CreditManagementService,
        package_service: CreditPackageService,
    ):
        """Handle one-time purchase completion"""
        try:
            # Get session details
            customer_id = checkout_session.get("customer")
            price_id = checkout_session.get("line_items").data[0].price.id

            # Get the credit package associated with this price ID
            credit_package = await package_service.get_package_by_platform_id(
                platform="stripe", product_id=price_id
            )

            # Get user by Stripe customer ID
            user = await self._get_user_by_stripe_customer_id(customer_id)

            # Add credits for the purchase
            await credit_service.add_credits(
                user_email=user.email,
                amount=credit_package["credits"],
                source=TransactionSource.STRIPE,
                platform_transaction_id=checkout_session.get("payment_intent"),
                package_id=credit_package["id"],
                metadata={
                    "stripe_session_id": checkout_session.get("id"),
                    "stripe_customer_id": customer_id,
                    "payment_status": checkout_session.get("payment_status"),
                },
            )

        except Exception as e:
            print(f"Error processing one-time purchase: {str(e)}")
            raise

    async def create_payment_intent(
        self, package_id: str, coupon_code: Optional[str] = None
    ):
        # Get the credit package associated with this price ID
        credit_package = await package_service.get_package_by_id(package_id)
        amount = credit_package["price"]
        currency = credit_package["currency"]

        # Create payment intent
        payment_intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            payment_method_types=["card"],
            metadata={"package_id": package_id},
        )

        return payment_intent
