import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.subscription.service import SubscriptionService
from app.api.subscription_config.service import SubscriptionConfigService
from app.auth.auth_handler import AuthHandler
from app.common.http_response_model import CommonResponse
from app.config import settings
from app.database import db_session
from app.models import SubscriptionConfiguration
from app.schemas import UpdateUser

router = APIRouter()


@router.get("/plans", name="Get all subscriptions plans")
async def get_subscription_plans(
    response: Response, session: AsyncSession = Depends(db_session)
) -> CommonResponse:

    try:
        subscription_service = SubscriptionService(session)
        subscriptions = await subscription_service.get_all_plans()
        payload = CommonResponse(
            message="Successfully fetched all subscriptions plans",
            success=True,
            payload=subscriptions,
        )
        return payload

    except HTTPException as http_err:
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.post("/stripe/webhook", name="Capture stripe webhook events")
async def get_stripe_events(
    response: Response, request: Request, session: AsyncSession = Depends(db_session)
):

    try:
        subscription_service = SubscriptionService(session)
        # endpoint_secret = "whsec_a784f2a316c03d04aa11ba781a586cdf62a6ee98a8cc8358e3d72da02c1eccc0"
        endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

        subscription_config_service = SubscriptionConfigService(session)

        event = None
        sig_header = request.headers.get("Stripe-Signature")
        payload = await request.body()
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        print("Event: ", event["type"])
        if event["type"] == "customer.deleted":
            customer = event["data"]["object"]
            email = customer["email"]
            await subscription_service.delete_stripe_customer_id(email)

        if event["type"] == "customer.created":
            customer = event["data"]["object"]
            customer_id = customer["id"]
            email = customer["email"]
            await subscription_service.add_stripe_customer_id(email, customer_id)

        # invoice.payment_succeeded
        if event["type"] == "invoice.payment_succeeded":
            payment_intent = event["data"]["object"]
            customer_id = payment_intent["customer"]
            status = payment_intent.get("status", None)
            user_subscription_data = UpdateUser(
                stripe_customer_id=customer_id, subscription_status=status
            )
            await subscription_service.update_user_subscription(user_subscription_data)

        if event["type"] == "customer.subscription.created":
            payment_intent = event["data"]["object"]
            subscription_id = payment_intent["id"]
            price_id = payment_intent["plan"]["id"]
            product_id = payment_intent["plan"]["product"]
            interval = payment_intent["plan"]["interval"]
            key = (
                payment_intent.get("items", {})
                .get("data", [{}])[0]
                .get("price", {})
                .get("lookup_key", "free")
            )
            customer_id = payment_intent["customer"]
            subscription_item_id = (
                payment_intent.get("items", {}).get("data", [{}])[0].get("id", None)
            )

            # get the configuration of the subscription based on the price id
            subscription_config: SubscriptionConfiguration = (
                await subscription_config_service.get_subscription_config_by_stripe_price_id(
                    price_id
                )
            )

            monthly_limit_ask_iah_queries = 0
            monthly_limit_craft_my_sonics = 0
            monthly_limit_sonic_supplement_shuffles = 0
            monthly_limit_super_sonic_shuffles = 0
            monthly_limit_ask_iah_playlist_generation = 0
            monthly_limit_ask_iah_image_generation = 0

            if subscription_config and interval == "month":
                monthly_limit_ask_iah_queries = (
                    subscription_config.numbers_of_ask_iah_queries
                )
                monthly_limit_craft_my_sonics = (
                    subscription_config.numbers_of_craft_my_sonics
                )
                monthly_limit_sonic_supplement_shuffles = (
                    subscription_config.numbers_of_sonic_supplement_shuffles
                )
                monthly_limit_super_sonic_shuffles = (
                    subscription_config.numbers_of_sonic_supplement_shuffles
                )
                monthly_limit_ask_iah_playlist_generation = (
                    subscription_config.numbers_of_ask_iah_playlist_generation
                )
                monthly_limit_ask_iah_image_generation = (
                    subscription_config.numbers_of_ask_iah_image_generation
                )
            elif subscription_config and interval == "year":
                monthly_limit_ask_iah_queries = (
                    subscription_config.numbers_of_ask_iah_queries * 12
                )
                monthly_limit_craft_my_sonics = (
                    subscription_config.numbers_of_craft_my_sonics * 12
                )
                monthly_limit_sonic_supplement_shuffles = (
                    subscription_config.numbers_of_sonic_supplement_shuffles * 12
                )
                monthly_limit_super_sonic_shuffles = (
                    subscription_config.numbers_of_sonic_supplement_shuffles * 12
                )
                monthly_limit_ask_iah_playlist_generation = (
                    subscription_config.numbers_of_ask_iah_playlist_generation * 12
                )
                monthly_limit_ask_iah_image_generation = (
                    subscription_config.numbers_of_ask_iah_image_generation * 12
                )

            status = payment_intent.get("status", None)
            user_subscription_data = UpdateUser(
                stripe_customer_id=customer_id,
                stripe_price_id=price_id,
                stripe_product_id=product_id,
                payment_interval=interval,
                subscription_id=subscription_id,
                subscription_item_id=subscription_item_id,
                active_subscription_id=price_id,
                subscription_plan=key,
                subscription_status=status,
                monthly_limit_ask_iah_queries=monthly_limit_ask_iah_queries,
                monthly_limit_craft_my_sonics=monthly_limit_craft_my_sonics,
                monthly_limit_sonic_supplement_shuffles=monthly_limit_sonic_supplement_shuffles,
                monthly_limit_super_sonic_shuffles=monthly_limit_super_sonic_shuffles,
                monthly_limit_ask_iah_playlist_generation=monthly_limit_ask_iah_playlist_generation,
                monthly_limit_ask_iah_image_generation=monthly_limit_ask_iah_image_generation,
            )

            await subscription_service.update_user_subscription(user_subscription_data)

        if event["type"] == "customer.subscription.updated":
            payment_intent = event["data"]["object"]
            subscription_id = payment_intent["id"]
            price_id = payment_intent["plan"]["id"]
            product_id = payment_intent["plan"]["product"]
            interval = payment_intent["plan"]["interval"]
            key = (
                payment_intent.get("items", {})
                .get("data", [{}])[0]
                .get("price", {})
                .get("lookup_key", "free")
            )
            customer_id = payment_intent["customer"]
            cancel_at = payment_intent.get("cancel_at", None)
            status = payment_intent.get("status", "null")
            subscription_item_id = (
                payment_intent.get("items", {}).get("data", [{}])[0].get("id", "null")
            )

            cancel_at_value = None
            subscription_cancel_id_value = None
            numbers_of_ask_iah_queries = None
            numbers_of_craft_my_sonics = None
            numbers_of_sonic_supplement_shuffles = None
            numbers_of_super_sonic_shuffles = None
            numbers_of_ask_iah_playlist_generation = None

            if cancel_at is not None:
                cancel_at_value = int(cancel_at)
                subscription_cancel_id_value = f"{price_id}:{cancel_at}"
            else:
                numbers_of_ask_iah_queries = 0
                numbers_of_craft_my_sonics = 0
                numbers_of_sonic_supplement_shuffles = 0
                numbers_of_super_sonic_shuffles = 0
                numbers_of_ask_iah_playlist_generation = 0
                cancel_at_value = 0
                subscription_cancel_id_value = "null"

            subscription_config: SubscriptionConfiguration = (
                await subscription_config_service.get_subscription_config_by_stripe_price_id(
                    price_id
                )
            )

            monthly_limit_ask_iah_queries = 0
            monthly_limit_craft_my_sonics = 0
            monthly_limit_sonic_supplement_shuffles = 0
            monthly_limit_super_sonic_shuffles = 0
            monthly_limit_ask_iah_playlist_generation = 0
            monthly_limit_ask_iah_image_generation = 0

            if subscription_config and interval == "month":
                monthly_limit_ask_iah_queries = (
                    subscription_config.numbers_of_ask_iah_queries
                )
                monthly_limit_craft_my_sonics = (
                    subscription_config.numbers_of_craft_my_sonics
                )
                monthly_limit_sonic_supplement_shuffles = (
                    subscription_config.numbers_of_sonic_supplement_shuffles
                )
                monthly_limit_super_sonic_shuffles = (
                    subscription_config.numbers_of_sonic_supplement_shuffles
                )
                monthly_limit_ask_iah_playlist_generation = (
                    subscription_config.numbers_of_ask_iah_playlist_generation
                )
                monthly_limit_ask_iah_image_generation = (
                    subscription_config.numbers_of_ask_iah_image_generation
                )
            elif subscription_config and interval == "year":
                monthly_limit_ask_iah_queries = (
                    subscription_config.numbers_of_ask_iah_queries * 12
                )
                monthly_limit_craft_my_sonics = (
                    subscription_config.numbers_of_craft_my_sonics * 12
                )
                monthly_limit_sonic_supplement_shuffles = (
                    subscription_config.numbers_of_sonic_supplement_shuffles * 12
                )
                monthly_limit_super_sonic_shuffles = (
                    subscription_config.numbers_of_sonic_supplement_shuffles * 12
                )
                monthly_limit_ask_iah_playlist_generation = (
                    subscription_config.numbers_of_ask_iah_playlist_generation * 12
                )
                monthly_limit_ask_iah_image_generation = (
                    subscription_config.numbers_of_ask_iah_image_generation * 12
                )

            user_subscription_data = UpdateUser(
                stripe_customer_id=customer_id,
                stripe_price_id=price_id,
                stripe_product_id=product_id,
                payment_interval=interval,
                subscription_id=subscription_id,
                subscription_item_id=subscription_item_id,
                active_subscription_id=price_id,
                subscription_cancel_at=cancel_at_value,
                subscription_cancel_id=subscription_cancel_id_value,
                subscription_plan=key,
                subscription_status=status,
                monthly_limit_ask_iah_queries=monthly_limit_ask_iah_queries,
                monthly_limit_craft_my_sonics=monthly_limit_craft_my_sonics,
                monthly_limit_sonic_supplement_shuffles=monthly_limit_sonic_supplement_shuffles,
                monthly_limit_super_sonic_shuffles=monthly_limit_super_sonic_shuffles,
                monthly_limit_ask_iah_playlist_generation=monthly_limit_ask_iah_playlist_generation,
                monthly_limit_ask_iah_image_generation=monthly_limit_ask_iah_image_generation,
                numbers_of_ask_iah_queries=numbers_of_ask_iah_queries,
                numbers_of_craft_my_sonics=numbers_of_craft_my_sonics,
                numbers_of_sonic_supplement_shuffles=numbers_of_sonic_supplement_shuffles,
                numbers_of_super_sonic_shuffles=numbers_of_super_sonic_shuffles,
                numbers_of_ask_iah_playlist_generation=numbers_of_ask_iah_playlist_generation,
            )

            await subscription_service.update_user_subscription(user_subscription_data)

        if event["type"] == "customer.subscription.deleted":
            payment_intent = event["data"]["object"]
            customer_id = payment_intent["customer"]
            status = payment_intent.get("status", None)

            monthly_limit_ask_iah_queries = 0
            monthly_limit_craft_my_sonics = 0
            monthly_limit_sonic_supplement_shuffles = 0
            monthly_limit_super_sonic_shuffles = 0
            monthly_limit_ask_iah_playlist_generation = 0
            monthly_limit_ask_iah_image_generation = 0

            user_subscription_data = UpdateUser(
                stripe_customer_id=customer_id,
                stripe_price_id="null",
                stripe_product_id="null",
                payment_interval="null",
                subscription_id="null",
                subscription_item_id="null",
                active_subscription_id="null",
                subscription_cancel_id="null",
                subscription_plan="free",
                subscription_status=status,
                monthly_limit_ask_iah_queries=monthly_limit_ask_iah_queries,
                monthly_limit_craft_my_sonics=monthly_limit_craft_my_sonics,
                monthly_limit_sonic_supplement_shuffles=monthly_limit_sonic_supplement_shuffles,
                monthly_limit_super_sonic_shuffles=monthly_limit_super_sonic_shuffles,
                monthly_limit_ask_iah_playlist_generation=monthly_limit_ask_iah_playlist_generation,
                monthly_limit_ask_iah_image_generation=monthly_limit_ask_iah_image_generation,
            )

            await subscription_service.update_user_subscription(user_subscription_data)

        return True

    except HTTPException as http_err:
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get("/customer-status", name="Get user subscription details")
async def get_user_subscriptions_details(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):

    try:
        subscription_service = SubscriptionService(session)
        customer_details = await subscription_service.get_user_subscription(email)
        payload = CommonResponse(
            message="Successfully fetched customer details",
            success=True,
            payload=customer_details,
        )
        return payload

    except HTTPException as http_err:
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        print(e)
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload
