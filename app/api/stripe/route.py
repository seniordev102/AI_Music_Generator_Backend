from typing import Annotated

import stripe
import stripe.error
from fastapi import APIRouter, Depends, Header, HTTPException, Path, Request, status
from fastapi.responses import Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.credit_management.service import CreditManagementService
from app.api.credit_packages.service import CreditPackageService
from app.api.stripe.service import IAHStripeService
from app.auth.auth_handler import AuthHandler
from app.common.http_response_model import CommonResponse
from app.common.logger import logger
from app.config import settings
from app.database import db_session
from app.schemas import (
    AuthenticateAffiliateUser,
    CreateAffiliateStripeSubscription,
    CreateIAHAffiliateUser,
    CreateStripeSubscription,
    GetStripeCoupon,
    UpdateStripeSubscription,
    ValidateStripeUser,
)

router = APIRouter()


@router.get("/key", name="Get stripe publisher key")
async def get_stripe_publisher_key(
    response: Response,
    x_stripe_key: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(db_session),
):
    try:
        if not x_stripe_key:
            raise HTTPException(status_code=400, detail="Missing 'x-stripe-key' header")

        if x_stripe_key != settings.STRIPE_ENCRYPTION_KEY:
            raise HTTPException(
                status_code=400,
                detail="Invalid stripe encryption key please contact admin",
            )
        iah_stripe_service = IAHStripeService(session)
        key = iah_stripe_service.get_stripe_publisher_key()
        payload = CommonResponse(
            success=True, message="Stripe publisher key fetched", payload=key
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get("/products", name="Get all active stripe products")
async def get_all_active_products(
    response: Response,
    x_stripe_key: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(db_session),
):
    try:
        if not x_stripe_key:
            raise HTTPException(status_code=400, detail="Missing 'x-stripe-key' header")

        if x_stripe_key != settings.STRIPE_ENCRYPTION_KEY:
            raise HTTPException(
                status_code=400,
                detail="Invalid stripe encryption key please contact admin",
            )

        iah_stripe_service = IAHStripeService(session)
        products = await iah_stripe_service.get_active_stripe_products()
        payload = CommonResponse(
            success=True, message="Stripe products fetched", payload=products
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get("/customer", name="Get stripe customer ID")
async def get_stripe_customer_id(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:

        iah_stripe_service = IAHStripeService(session)
        customer_id = await iah_stripe_service.get_or_create_stripe_customer_id(
            email=email
        )
        payload = CommonResponse(
            success=True,
            message="Stripe customer id has been fetched",
            payload=customer_id,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get("/coupons", name="Get all stripe coupons")
async def get_all_stripe_coupons(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:
        iah_stripe_service = IAHStripeService(session)
        coupons = await iah_stripe_service.list_all_stripe_coupons()
        payload = CommonResponse(
            success=True,
            message="Stripe coupons have been fetched",
            payload=coupons,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get("/coupon/{coupon_id}", name="Get stripe coupon by id")
async def get_stripe_coupon_by_id(
    response: Response,
    email: str = Depends(AuthHandler()),
    coupon_id: str = Path(..., title="Stripe coupon ID"),
    session: AsyncSession = Depends(db_session),
):
    try:
        iah_stripe_service = IAHStripeService(session)
        coupon = await iah_stripe_service.get_stripe_coupon_by_id(coupon_id=coupon_id)
        payload = CommonResponse(
            success=True,
            message="Stripe coupon has been fetched",
            payload=coupon,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.post("/coupon-name", name="Get stripe coupon coupon name")
async def get_stripe_coupon_by_id(
    request: GetStripeCoupon,
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:
        iah_stripe_service = IAHStripeService(session)
        coupon = await iah_stripe_service.get_stripe_coupon_by_name(
            coupon_name=request.coupon_name
        )
        payload = CommonResponse(
            success=True,
            message="Stripe coupon has been fetched",
            payload=coupon,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.post("/create-subscription", name="stripe create a subscription")
async def create_user_subscription(
    request: CreateStripeSubscription,
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:
        iah_stripe_service = IAHStripeService(session)
        subscription_details = await iah_stripe_service.create_stripe_subscription(
            price_id=request.price_id,
            customer_id=request.customer_id,
            coupon_id=request.coupon_id,
        )
        payload = CommonResponse(
            success=True,
            message="Stripe subscription has been created",
            payload=subscription_details,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get("/subscription-status", name="Get user subscription status")
async def get_user_subscription_details(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:
        iah_stripe_service = IAHStripeService(session)
        subscription_detail = await iah_stripe_service.get_user_subscription_status(
            email=email
        )
        payload = CommonResponse(
            success=True,
            message="User subscription details fetched",
            payload=subscription_detail,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get("/payment-methods", name="Get payment method details of the user")
async def get_user_subscription_details(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:
        iah_stripe_service = IAHStripeService(session)
        payment_methods = await iah_stripe_service.get_stripe_customer_payment_methods(
            email=email
        )
        payload = CommonResponse(
            success=True,
            message="User payment methods details fetched",
            payload=payment_methods,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.post(
    "/payment-methods/{payment_method_id}/detach",
    name="Detach payment method from the customer",
)
async def detach_payment_method_from_customer(
    response: Response,
    email: str = Depends(AuthHandler()),
    payment_method_id: str = Path(..., title="Stripe payment method id"),
    session: AsyncSession = Depends(db_session),
):
    try:
        iah_stripe_service = IAHStripeService(session)
        detach_response = await iah_stripe_service.detach_payment_method_from_customer(
            email=email, payment_method_id=payment_method_id
        )
        payload = CommonResponse(
            success=True,
            message="User payment methods detached from customer",
            payload=detach_response,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.post(
    "/subscription/{subscription_id}/cancel",
    name="Cancel user subscription at period end",
)
async def cancel_user_subscription(
    response: Response,
    email: str = Depends(AuthHandler()),
    subscription_id: str = Path(..., title="Stripe subscription id"),
    session: AsyncSession = Depends(db_session),
):
    try:
        iah_stripe_service = IAHStripeService(session)
        result = await iah_stripe_service.cancel_user_subscriptions(
            email=email, subscription_id=subscription_id
        )
        payload = CommonResponse(
            success=True,
            message="User subscription has been canceled at period end",
            payload=result,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.post(
    "/subscription/{subscription_id}/resume",
    name="Resume user subscription",
)
async def resume_user_subscription(
    response: Response,
    email: str = Depends(AuthHandler()),
    subscription_id: str = Path(..., title="Stripe subscription id"),
    session: AsyncSession = Depends(db_session),
):
    try:
        iah_stripe_service = IAHStripeService(session)
        result = await iah_stripe_service.resume_user_subscriptions(
            email=email, subscription_id=subscription_id
        )
        payload = CommonResponse(
            success=True,
            message="User subscription has been resumed",
            payload=result,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.post("/update-subscription", name="Update existing stripe subscription")
async def update_existing_user_subscription(
    request: UpdateStripeSubscription,
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
):
    try:
        iah_stripe_service = IAHStripeService(session)
        subscription_details = await iah_stripe_service.update_user_subscription(
            email=email,
            subscription_id=request.subscription_id,
            new_price_id=request.new_price_id,
            coupon_id=request.coupon_id,
        )
        payload = CommonResponse(
            success=True,
            message="Stripe subscription has been updated",
            payload=subscription_details,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.post(
    "/affiliate/create-user", name="Affiliate create user with stripe customer intent"
)
async def create_user_subscription(
    request: CreateIAHAffiliateUser,
    response: Response,
    session: AsyncSession = Depends(db_session),
):
    try:
        iah_stripe_service = IAHStripeService(session)
        user = await iah_stripe_service.create_iah_affiliate_user(
            email=request.email, name=request.name, password=request.password
        )
        payload = CommonResponse(
            success=True,
            message="IAH affiliate user has been created",
            payload=user,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.post(
    "/affiliate/create-subscription", name="Affiliate stripe subscription create"
)
async def create_user_subscription(
    request: CreateAffiliateStripeSubscription,
    response: Response,
    session: AsyncSession = Depends(db_session),
):
    try:
        iah_stripe_service = IAHStripeService(session)
        subscription_details = (
            await iah_stripe_service.create_iah_affiliate_subscription(
                customer_id=request.customer_id,
                payment_method_id=request.payment_method_id,
                price_id=request.price_id,
                coupon_code=request.coupon_code,
            )
        )
        payload = CommonResponse(
            success=True,
            message="IAH affiliate subscription has been created",
            payload=subscription_details,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.post("/affiliate/coupon-name", name="Get stripe coupon coupon name")
async def get_stripe_coupon_by_id(
    request: GetStripeCoupon,
    response: Response,
    x_stripe_key: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(db_session),
):
    try:
        if not x_stripe_key:
            raise HTTPException(status_code=400, detail="Missing 'x-stripe-key' header")

        if x_stripe_key != settings.STRIPE_ENCRYPTION_KEY:
            raise HTTPException(
                status_code=400,
                detail="Invalid stripe encryption key please contact admin",
            )
        iah_stripe_service = IAHStripeService(session)
        coupon = await iah_stripe_service.get_stripe_coupon_by_name(
            coupon_name=request.coupon_name
        )
        payload = CommonResponse(
            success=True,
            message="Stripe coupon has been fetched",
            payload=coupon,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.post(
    "/affiliate/check-stripe-user", name="Check and validate stripe user account"
)
async def validate_stripe_user(
    request: ValidateStripeUser,
    response: Response,
    session: AsyncSession = Depends(db_session),
):
    try:
        iah_stripe_service = IAHStripeService(session)
        stripe_customer = await iah_stripe_service.validate_stripe_user_account(
            email=request.email
        )
        payload = CommonResponse(
            success=True,
            message="Stripe customer has been fetched",
            payload=stripe_customer,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.post("/affiliate/authenticate", name="Authenticate stripe customer")
async def authenticate_affiliate_user(
    request: AuthenticateAffiliateUser,
    response: Response,
    session: AsyncSession = Depends(db_session),
):
    try:
        iah_stripe_service = IAHStripeService(session)
        stripe_customer = await iah_stripe_service.authenticate_affiliate_user(
            email=request.email, password=request.password
        )
        payload = CommonResponse(
            success=True,
            message="User has been authenticated",
            payload=stripe_customer,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.post("/webhook", name="Stripe webhook handler")
async def stripe_webhook_handler(
    response: Response,
    request: Request,
    session: AsyncSession = Depends(db_session),
):
    try:
        # Get the raw request body
        body = await request.body()
        # Get Stripe signature from headers
        signature = request.headers.get("stripe-signature")

        try:
            # Verify webhook signature
            event = stripe.Webhook.construct_event(
                payload=body,
                sig_header=signature,
                secret=settings.STRIPE_WEBHOOK_SECRET,
            )
        except stripe.error.SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Invalid signature")

        # Initialize services
        credit_service = CreditManagementService(session)
        package_service = CreditPackageService(session)

        stripe_service = IAHStripeService(session)

        # Handle different event types
        if event.type == "invoice.paid":
            # Handle subscription renewal
            await stripe_service.handle_subscription_renewal(
                event.data.object, credit_service, package_service
            )
        elif event.type == "checkout.session.completed":
            # Handle one-time purchase
            await stripe_service.handle_one_time_purchase(
                event.data.object, credit_service, package_service
            )

        payload = CommonResponse(
            success=True,
            message="Webhook event has been handled successfully",
            payload=None,
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except Exception as e:
        logger.error(f"An error occurred while calling stripe webhook: {e}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload
