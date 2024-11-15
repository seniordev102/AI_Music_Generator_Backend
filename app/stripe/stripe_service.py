import stripe

from app.config import settings


class StripeService:
    def __init__(self) -> None:
        stripe.set_app_info(
            "iah admin api", version="0.0.1", url="https://iahadminapi.herokuapp.com"
        )
        stripe.api_key = settings.STRIPE_SECRET_KEY
        stripe.api_version = settings.STRIPE_API_VERSION
        self.subscription_plans = ["premium", "commercial"]
        self.stripe = stripe

    def get_subscription_plans(self):
        return self.stripe.Price.list(lookup_keys=self.subscription_plans)

    def create_customer(self, email: str, name: str):
        return self.stripe.Customer.create(
            email=email,
            name=name,
        )

    def subscription_details_by_id(self, subscription_id: str):
        return self.stripe.Subscription.retrieve(subscription_id)
