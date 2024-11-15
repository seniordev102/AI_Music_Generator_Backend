import stripe
import stripe.error
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.requests import Request
from fastapi.responses import Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.credit_management.stripe.service import StripeCreditManagementService
from app.auth.auth_handler import AuthHandler
from app.common.http_response_model import CommonResponse
from app.config import settings
from app.database import db_session
from app.logger.logger import logger
from app.schemas import CreatePaymentIntent, ValidateStripeCouponCode

router = APIRouter()


@router.post("/create-intent", name="Create stripe payment intent")
async def create_payment_intent(
    request: CreatePaymentIntent,
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
) -> CommonResponse:
    try:
        cm_service = StripeCreditManagementService(session)
        result = await cm_service.create_payment_intent(
            package_id=request.package_id,
            email=email,
            coupon_name=request.coupon_name,
            original_amount=request.original_amount,
            payable_amount=request.payable_amount,
            selected_payment_method_id=request.selected_payment_method_id,
        )
        payload = CommonResponse(
            success=True,
            message="Payment intent created successfully",
            payload=result,
        )
        response.status_code = status.HTTP_200_OK
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


@router.post("/validate-coupon", name="Validate coupon code by coupon name")
async def validate_coupon_by_name(
    request: ValidateStripeCouponCode,
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
) -> CommonResponse:
    try:
        cm_service = StripeCreditManagementService(session)
        result = await cm_service.validate_coupon_by_name(
            coupon_name=request.coupon_name,
            original_price=request.original_price,
        )
        payload = CommonResponse(
            success=True,
            message="Coupon code validated successfully",
            payload=result,
        )
        response.status_code = status.HTTP_200_OK
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


@router.get("/payment-methods", name="Get stripe customer payment methods")
async def get_payment_methods(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
) -> CommonResponse:
    try:
        cm_service = StripeCreditManagementService(session)
        result = await cm_service.get_stripe_customer_payment_methods(email=email)
        payload = CommonResponse(
            success=True,
            message="Payment methods fetched successfully",
            payload=result,
        )
        response.status_code = status.HTTP_200_OK
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


@router.get(
    "/remove-duplicate-payment-methods",
    name="Remove duplicate payment methods for customer",
)
async def remove_duplicate_payment_methods(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
) -> CommonResponse:
    try:
        cm_service = StripeCreditManagementService(session)
        result = await cm_service.remove_duplicate_payment_methods(email=email)
        payload = CommonResponse(
            success=True,
            message="Duplicate payment methods removed successfully",
            payload=result,
        )
        response.status_code = status.HTTP_200_OK
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


@router.post("/webhook", name="Handle Stripe webhook events")
async def handle_stripe_webhook(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(db_session),
) -> CommonResponse:
    try:
        # Get the webhook signature from the request headers
        signature = request.headers.get("stripe-signature")
        if not signature:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing Stripe signature",
            )

        # Get the request body
        payload = await request.body()
        payload_str = payload.decode("utf-8")

        # Verify the webhook signature
        try:
            event = stripe.Webhook.construct_event(
                payload_str, signature, settings.STRIPE_WEBHOOK_SECRET
            )
        except stripe.error.SignatureVerificationError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Stripe signature",
            )

        # Process the event
        cm_service = StripeCreditManagementService(session)
        event_type = event["type"]
        event_data = event["data"]["object"]

        logger.info(f"Processing Stripe webhook event: {event_type}")

        # Handle different event types
        if event_type == "payment_intent.succeeded":
            await cm_service.handle_successful_payment(event_data)
            message = "Payment intent succeeded event processed"
        elif event_type == "invoice.payment_succeeded":
            await cm_service.handle_invoice_payment_succeeded(event_data)
            message = "Invoice payment succeeded event processed"
        elif event_type == "customer.subscription.created":
            await cm_service.handle_subscription_created(event_data)
            message = "Subscription created event processed"
        elif event_type == "customer.subscription.updated":
            await cm_service.handle_subscription_updated(event_data)
            message = "Subscription updated event processed"
        elif event_type == "customer.subscription.deleted":
            await cm_service.handle_subscription_deleted(event_data)
            message = "Subscription deleted event processed"
        else:
            message = f"Unhandled event type: {event_type}"
            logger.info(message)

        payload = CommonResponse(
            success=True,
            message=message,
            payload={"event_type": event_type},
        )
        response.status_code = status.HTTP_200_OK
        return payload

    except HTTPException as http_err:
        payload = CommonResponse(
            success=False, message=str(http_err.detail), payload=None
        )
        response.status_code = http_err.status_code
        return payload

    except Exception as e:
        logger.error(f"Error processing Stripe webhook: {str(e)}")
        payload = CommonResponse(success=False, message=str(e), payload=None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return payload


@router.get(
    "/user/subscription",
    name="Get current active subscription of the user",
)
async def get_current_active_subscription_details(
    response: Response,
    email: str = Depends(AuthHandler()),
    session: AsyncSession = Depends(db_session),
) -> CommonResponse:
    try:
        cm_service = StripeCreditManagementService(session)
        result = await cm_service.get_current_user_active_subscription(email=email)
        payload = CommonResponse(
            success=True,
            message="User subscription details fetched successfully",
            payload=result,
        )
        response.status_code = status.HTTP_200_OK
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
