import os
import random
import string
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import boto3
from fastapi import Depends, HTTPException, status
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.subscription_config.service import SubscriptionConfigService
from app.auth.auth_handler import AuthHandler
from app.auth.token_handler import JWTTokenHandler
from app.config import settings
from app.database import db_session
from app.models import (
    CreditPackage,
    CreditTransaction,
    SubscriptionConfiguration,
    TransactionSource,
    TransactionType,
    User,
    UserCreditBalance,
)
from app.schemas import CreateUser, SsoUserLoginRequest
from app.stripe.stripe_service import StripeService


class AuthService:
    def __init__(
        self,
        session: AsyncSession = Depends(db_session),
        token_handler: JWTTokenHandler = JWTTokenHandler(),
        stripe_service=StripeService(),
        auth_handler: AuthHandler = AuthHandler(),
    ) -> None:
        self.session = session
        self.SECRET_KEY = settings.JWT_SECRET_KEY
        self.ALGORITHM = settings.JWT_ALGORITHM
        self.ACCESS_TOKEN_EXPIRE_MINUTES = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        self.REFRESH_TOKEN_EXPIRE_MINUTES = settings.JWT_REFRESH_TOKEN_EXPIRE_MINUTES
        self.EMAIL_EXPIRE_TIME_IN_SECONDS = settings.EMAIL_EXPIRE_SECONDS
        self.token_handler = token_handler
        self.auth_handler = auth_handler
        self.stripe_service = stripe_service

    async def get_user_by_email(self, email: str) -> User:

        email_lower_case = email.lower()
        user_record = await self.session.execute(
            select(User).where(User.email == email_lower_case)
        )
        user = user_record.scalar_one_or_none()
        return user

    # create a new user

    async def create_user(self, new_user: CreateUser) -> User:
        user = await self.get_user_by_email(new_user.email)
        if user:
            raise HTTPException(
                status_code=400, detail="User with this email already exists"
            )

        # hash password before saving into the db
        hashed_password = self.auth_handler.hash_password(new_user.password)

        # create stripe customer
        customer = self.stripe_service.create_customer(new_user.email, new_user.name)

        subscription_config_service = SubscriptionConfigService(self.session)
        config: SubscriptionConfiguration = (
            await subscription_config_service.get_subscription_config_by_stripe_price_id(
                "free_monthly"
            )
        )

        if (
            new_user.invite_code is not None
            and new_user.invite_code != ""
            and (new_user.invite_code == "369369" or new_user.invite_code == "528528")
        ):
            monthly_limit_ask_iah_queries = 100000
            monthly_limit_craft_my_sonics = 100000
            monthly_limit_sonic_supplement_shuffles = 100000
            monthly_limit_super_sonic_shuffles = 100000
            monthly_limit_ask_iah_playlist_generation = 100000
            monthly_limit_ask_iah_image_generation = 100000
        else:
            monthly_limit_ask_iah_queries = config.numbers_of_ask_iah_queries
            monthly_limit_craft_my_sonics = config.numbers_of_craft_my_sonics
            monthly_limit_sonic_supplement_shuffles = (
                config.numbers_of_sonic_supplement_shuffles
            )
            monthly_limit_super_sonic_shuffles = config.numbers_of_super_sonic_shuffles
            monthly_limit_ask_iah_playlist_generation = (
                config.numbers_of_ask_iah_playlist_generation
            )
            monthly_limit_ask_iah_image_generation = (
                config.numbers_of_ask_iah_image_generation
            )

        user = User(
            name=new_user.name,
            email=new_user.email.lower(),
            hashed_password=hashed_password,
            stripe_customer_id=customer.id,
            monthly_limit_ask_iah_queries=monthly_limit_ask_iah_queries,
            monthly_limit_craft_my_sonics=monthly_limit_craft_my_sonics,
            monthly_limit_sonic_supplement_shuffles=monthly_limit_sonic_supplement_shuffles,
            monthly_limit_super_sonic_shuffles=monthly_limit_super_sonic_shuffles,
            monthly_limit_ask_iah_playlist_generation=monthly_limit_ask_iah_playlist_generation,
            monthly_limit_ask_iah_image_generation=monthly_limit_ask_iah_image_generation,
            invite_code=new_user.invite_code if new_user.invite_code else None,
        )

        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)

        # Add signup bonus credits
        await self._add_signup_bonus_credits(user, source="regular")

        return user

    async def authenticate_user(self, email: str, password: str) -> User:
        user = await self.get_user_by_email(email)

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        is_valid_password = self.auth_handler.verify_password(
            password, user.hashed_password
        )
        if not is_valid_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token = self.token_handler.create_access_token(data={"sub": user.email})
        refresh_token = self.token_handler.create_refresh_token(
            data={"sub": user.email}
        )
        return {
            "user": user,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    async def get_access_token_using_refresh_token(self, refresh_token: str):

        email = await self.token_handler.validate_refresh_token(refresh_token)
        user = await self.get_user_by_email(email)

        if user is None:
            raise HTTPException(status_code=400, detail="User not found")

        access_token = self.token_handler.create_access_token(data={"sub": user.email})
        return {"access_token": access_token, "token_type": "bearer"}

    async def login_sso_user(self, sso_user: SsoUserLoginRequest):
        # check if user exists for given email and provider is null
        user = await self.get_user_by_email(sso_user.email)

        if user is None:
            # create a new user with random password
            password = self.auth_handler.generate_random_password()
            hashed_password = self.auth_handler.hash_password(str(password))

            # create stripe customer
            customer = self.stripe_service.create_customer(
                sso_user.email, sso_user.name
            )

            subscription_config_service = SubscriptionConfigService(self.session)
            config: SubscriptionConfiguration = (
                await subscription_config_service.get_subscription_config_by_stripe_price_id(
                    "free_monthly"
                )
            )

            if (
                sso_user.invite_code is not None
                and sso_user.invite_code != ""
                and (
                    sso_user.invite_code == "369369" or sso_user.invite_code == "528528"
                )
            ):
                monthly_limit_ask_iah_queries = 100000
                monthly_limit_craft_my_sonics = 100000
                monthly_limit_sonic_supplement_shuffles = 100000
                monthly_limit_super_sonic_shuffles = 100000
                monthly_limit_ask_iah_playlist_generation = 100000
                monthly_limit_ask_iah_image_generation = 100000
            else:
                monthly_limit_ask_iah_queries = config.numbers_of_ask_iah_queries
                monthly_limit_craft_my_sonics = config.numbers_of_craft_my_sonics
                monthly_limit_sonic_supplement_shuffles = (
                    config.numbers_of_sonic_supplement_shuffles
                )
                monthly_limit_super_sonic_shuffles = (
                    config.numbers_of_super_sonic_shuffles
                )
                monthly_limit_ask_iah_playlist_generation = (
                    config.numbers_of_ask_iah_playlist_generation
                )
                monthly_limit_ask_iah_image_generation = (
                    config.numbers_of_ask_iah_image_generation
                )

            user = User(
                name=sso_user.name,
                email=sso_user.email.lower(),
                hashed_password=hashed_password,
                profile_image=sso_user.image,
                provider=sso_user.provider,
                provider_id=sso_user.provider_id,
                stripe_customer_id=customer.id,
                monthly_limit_ask_iah_queries=monthly_limit_ask_iah_queries,
                monthly_limit_craft_my_sonics=monthly_limit_craft_my_sonics,
                monthly_limit_sonic_supplement_shuffles=monthly_limit_sonic_supplement_shuffles,
                monthly_limit_super_sonic_shuffles=monthly_limit_super_sonic_shuffles,
                monthly_limit_ask_iah_playlist_generation=monthly_limit_ask_iah_playlist_generation,
                monthly_limit_ask_iah_image_generation=monthly_limit_ask_iah_image_generation,
                invite_code=sso_user.invite_code if sso_user.invite_code else None,
            )

            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)

            # Add signup bonus credits for new SSO users
            await self._add_signup_bonus_credits(user, source="sso")

            access_token = self.token_handler.create_access_token(
                data={"sub": user.email}
            )
            refresh_token = self.token_handler.create_refresh_token(
                data={"sub": user.email}
            )
            return {
                "user": user,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
            }

        else:

            stripe_customer_id = None
            if user.stripe_customer_id is None:
                customer = self.stripe_service.create_customer(
                    sso_user.email, sso_user.name
                )
                stripe_customer_id = customer.id
            else:
                stripe_customer_id = user.stripe_customer_id

            # update user with provider and provider_id
            user.provider = sso_user.provider
            user.provider_id = sso_user.provider_id
            user.stripe_customer_id = stripe_customer_id

            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)
            access_token = self.token_handler.create_access_token(
                data={"sub": user.email}
            )
            refresh_token = self.token_handler.create_refresh_token(
                data={"sub": user.email}
            )
            return {
                "user": user,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
            }

    async def send_reset_password_email(self, email: str, origin: str):

        # get the user by email
        user = await self.get_user_by_email(email)

        if user is None:
            raise HTTPException(
                status_code=400,
                detail="No account exists with this email address. Please check the email or sign up for a new account.",
            )

        if user.provider is not None:
            raise HTTPException(
                status_code=400,
                detail="This account uses social login. Please sign in with your social provider.",
            )

        token = self._generate_random_string(length=40)
        reset_link = f"{origin}/reset-password?token={token}"

        # update the user table with token and password rest at timestamp
        user.email_rest_token = token
        user.email_rest_at = datetime.now(timezone.utc)
        self.session.add(user)
        await self.session.commit()

        template_dir = os.path.join(os.path.dirname(__file__), "email_templates")
        env = Environment(loader=FileSystemLoader(template_dir))

        SENDER = "hello@iah.fit"
        RECIPIENT = email
        SUBJECT = "Password Reset Request"

        template = env.get_template("password_rest.html")
        BODY_HTML = template.render(reset_link=reset_link)
        msg = MIMEMultipart("alternative")
        msg["Subject"] = SUBJECT
        msg["From"] = SENDER
        msg["To"] = RECIPIENT

        part = MIMEText(BODY_HTML, "html")
        msg.attach(part)

        client = boto3.client(
            "ses",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_DEFAULT_REGION,
        )

        response = client.send_raw_email(
            Source=SENDER,
            Destinations=[RECIPIENT],
            RawMessage={"Data": msg.as_string()},
        )

        if response["ResponseMetadata"]["HTTPStatusCode"] != 200:
            raise HTTPException(
                status_code=400, detail="Failed to send password reset email"
            )
        message_id = response["MessageId"]
        return message_id

    async def rest_user_password(self, password: str, email: str, token: str):
        query = (
            select(User)
            .where(User.email_rest_token == token)
            .where(User.email == email)
        )

        user_record = await self.session.execute(query)
        user: User = user_record.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=400,
                detail="The password reset link is invalid. Please request a new link and try again.",
            )

        current_time_utc = datetime.now(timezone.utc)
        time_difference = current_time_utc - user.email_rest_at

        # Calculate time difference in minutes
        minutes_difference = time_difference.total_seconds()

        if minutes_difference > self.EMAIL_EXPIRE_TIME_IN_SECONDS:
            raise HTTPException(
                status_code=400,
                detail="The password reset link has expired. Please request a new link and try again.",
            )

        # update user password
        hashed_password = self.auth_handler.hash_password(password)
        user.hashed_password = hashed_password.decode("utf-8")
        user.email_rest_token = None
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)

        # sign in and get the user token
        access_token = self.token_handler.create_access_token(data={"sub": user.email})
        refresh_token = self.token_handler.create_refresh_token(
            data={"sub": user.email}
        )
        return {
            "user": user,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    async def get_user_subscription_status(self, email: str):
        user = await self.get_user_by_email(email)

        FUNDING_MEMBER_CODE = "528528"
        TEAM_MEMBER_CODE = "369369"
        # check if the user is founding member or team member
        if (
            user.invite_code is not None
            and user.invite_code == FUNDING_MEMBER_CODE
            or user.invite_code == TEAM_MEMBER_CODE
        ):
            return True

        # let's check if the user has any active subscription
        if user.active_subscription_id is not None:
            return True

        return False

    def _generate_random_string(self, length=12):
        characters = string.ascii_letters + string.digits
        return "".join(random.choices(characters, k=length))

    async def is_admin_check(self, email: str) -> bool:
        email_lower_case = email.lower()
        query = select(User).where(User.email == email_lower_case)
        user_record = await self.session.execute(query)
        user = user_record.scalar_one_or_none()

        if user is None:
            raise HTTPException(status_code=400, detail="User not found")

        if not user.is_admin:
            raise HTTPException(
                status_code=400,
                detail="User is not an admin only admin can perform this action",
            )
        return True

    async def _add_signup_bonus_credits(self, user: User, source: str = "regular"):
        """Add signup bonus credits to a new user"""
        try:
            from app.api.credit_management.service import CreditManagementService

            # Add credits directly to the user's account
            credit_service = CreditManagementService(self.session)

            # Get current balance
            current_time = datetime.now(timezone.utc)
            current_balance_query = select(
                func.sum(UserCreditBalance.remaining_amount)
            ).where(
                and_(
                    UserCreditBalance.user_id == user.id,
                    UserCreditBalance.is_active == True,
                    or_(
                        UserCreditBalance.expires_at > current_time,
                        UserCreditBalance.expires_at == None,
                    ),
                )
            )

            SIGN_UP_BONUS_AMOUNT = 100
            result = await self.session.execute(current_balance_query)
            current_balance = result.scalar() or 0
            new_balance = current_balance + SIGN_UP_BONUS_AMOUNT

            # Get the 333 Credits package for signup bonus
            signup_package = await credit_service._get_signup_bonus_package()

            # Create credit transaction
            transaction = CreditTransaction(
                user_id=user.id,
                transaction_type=TransactionType.CREDIT,
                transaction_source=TransactionSource.SYSTEM,
                amount=SIGN_UP_BONUS_AMOUNT,
                balance_after=new_balance,
                description="Signup bonus credits",
                package_id=str(signup_package.id),
                credit_metadata={"reason": "signup_bonus", "source": source},
            )
            self.session.add(transaction)
            await self.session.flush()  # Get transaction ID

            # Create credit balance record
            credit_balance = UserCreditBalance(
                user_id=user.id,
                package_id=signup_package.id,  # Use the 333 Credits package ID
                transaction_id=transaction.id,
                initial_amount=SIGN_UP_BONUS_AMOUNT,
                remaining_amount=SIGN_UP_BONUS_AMOUNT,
                expires_at=None,  # No expiration for signup bonus
                is_active=True,
            )
            self.session.add(credit_balance)
            await self.session.commit()

            return True
        except Exception as e:
            # Log the error but don't fail the user registration
            print(f"Error adding signup bonus credits: {str(e)}")
            return False
