import os
import random
import string

import stripe
from fastapi import Depends, HTTPException, status
from pydantic import EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.auth_handler import AuthHandler
from app.config import settings
from app.database import db_session
from app.email.service import EmailSender
from app.models import User
from app.schemas import CreateAffiliateUser


class UserAffiliateService:
    def __init__(
        self,
        session: AsyncSession = Depends(db_session),
        auth_handler: AuthHandler = AuthHandler(),
    ) -> None:
        stripe.set_app_info(
            "iah admin api", version="0.0.1", url="https://iahadminapi.herokuapp.com"
        )
        stripe.api_key = settings.STRIPE_SECRET_KEY
        stripe.api_version = settings.STRIPE_API_VERSION
        self.stripe = stripe
        self.session = session
        self.auth_handler = auth_handler
        self.email_sender = EmailSender()

    async def create_affiliate_user(self, affiliate_data: CreateAffiliateUser):
        # Extract Stripe customer details from Stripe email
        customers = stripe.Customer.list(email=affiliate_data.email)

        if len(customers["data"]) == 0:
            raise HTTPException(
                detail="Stripe customer not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        else:
            customer_details = customers["data"][0]
            customer_id = customer_details["id"]
            customer_name = customer_details.get("name")

        # Retrieve the customer's subscriptions
        subscriptions = stripe.Subscription.list(customer=customer_id)

        if len(subscriptions["data"]) == 0:
            raise HTTPException(
                detail="No subscriptions found for customer",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        else:
            # Assuming you want the most recent subscription
            subscription = subscriptions["data"][0]
            subscription_id = subscription["id"]
            subscription_status = subscription["status"]

            # Access the subscription items
            items = subscription["items"]["data"]
            if len(items) > 0:
                subscription_item = items[0]
                subscription_item_id = subscription_item["id"]

                # Retrieve the price ID and product ID
                price_id = subscription_item["price"]["id"]
                product_id = subscription_item["price"]["product"]

                # Retrieve the Price object to get the lookup_key
                price = stripe.Price.retrieve(price_id)
                unit_amount = price.get("unit_amount")
                currency = price.get("currency")
                lookup_key = price.get("lookup_key")

                # Retrieve the Product object if needed
                product = stripe.Product.retrieve(product_id)
                product_name = product.get("name")

                # Optionally, retrieve plan details if applicable
                plan = subscription_item.get("plan")
                if plan:
                    plan_id = plan["id"]
                    plan_nickname = plan.get("nickname")
            else:
                raise HTTPException(
                    detail="No subscription items found",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

        # check the user already exists for given email address
        user_record = await self.session.execute(
            select(User).where(User.email == affiliate_data.email.lower())
        )
        user: User = user_record.scalar_one_or_none()

        if user is not None:
            raise HTTPException(
                detail="User already exist skipping the user",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        else:
            # create the user
            random_password = self._generate_password(10)
            hashed_password = self.auth_handler.hash_password(random_password)

            monthly_limit_ask_iah_queries = 100000
            monthly_limit_craft_my_sonics = 100000
            monthly_limit_sonic_supplement_shuffles = 100000
            monthly_limit_super_sonic_shuffles = 100000
            monthly_limit_ask_iah_playlist_generation = 100000
            monthly_limit_ask_iah_image_generation = 100000

        payment_interval = None

        if lookup_key == "iah_premium_monthly_special":
            payment_interval = "monthly"
        else:
            payment_interval = "yearly"

        new_user = User(
            name=customer_name,
            email=affiliate_data.email.lower(),
            hashed_password=hashed_password,
            stripe_customer_id=customer_id,
            monthly_limit_ask_iah_queries=monthly_limit_ask_iah_queries,
            monthly_limit_craft_my_sonics=monthly_limit_craft_my_sonics,
            monthly_limit_sonic_supplement_shuffles=monthly_limit_sonic_supplement_shuffles,
            monthly_limit_super_sonic_shuffles=monthly_limit_super_sonic_shuffles,
            monthly_limit_ask_iah_playlist_generation=monthly_limit_ask_iah_playlist_generation,
            monthly_limit_ask_iah_image_generation=monthly_limit_ask_iah_image_generation,
            subscription_plan=lookup_key,
            subscription_id=subscription_id,
            subscription_item_id=subscription_item_id,
            stripe_price_id=price_id,
            stripe_product_id=product_id,
            active_subscription_id=price_id,
            subscription_status=subscription_status,
            payment_interval=payment_interval,
            subscription_cancel_at=0,
        )

        self.session.add(new_user)
        await self.session.commit()

        await self._send_onboarding_email(
            recipient=affiliate_data.email.lower(),
            name=customer_name,
            password=random_password,
            login_link="https://ask.iah.fit/login",
            privacy_policy_link="https://iah.fit/privacy-policy/",
            terms_of_service_link="https://iah.fit/terms-of-use/",
        )

    def _generate_password(self, length: int = 6) -> str:
        """Generates a random password using letters, digits, and '@', '#' symbols."""
        characters = string.ascii_letters + string.digits + "@#"
        password = "".join(random.choice(characters) for _ in range(length))
        return password

    async def _send_onboarding_email(
        self,
        recipient: EmailStr,
        name: str,
        password: str,
        login_link: str,
        privacy_policy_link: str,
        terms_of_service_link: str,
    ) -> bool:
        subject = "Welcome to IAH Fit - Your Account is Ready!"
        placeholders = {
            "name": name,
            "email": recipient,
            "password": password,
            "login_link": login_link,
            "privacy_policy_link": privacy_policy_link,
            "terms_of_service_link": terms_of_service_link,
        }

        current_dir = os.path.dirname(os.path.abspath(__file__))
        templates_dir = os.path.join(current_dir, "email_templates")
        template_path = os.path.join(templates_dir, "onboarding_template.html")

        return await self.email_sender.send_email_with_template(
            recipient=recipient,
            subject=subject,
            template_path=template_path,
            placeholders=placeholders,
        )
