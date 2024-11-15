from typing import Dict, List, Optional

from fastapi import Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import db_session
from app.models import CreditPackage, SubscriptionPeriod

# Define credit packages with platform-specific IDs
CREDIT_PACKAGES = {
    "pay_as_you_go": [
        {
            "name": "333 Credits",
            "credits": 333,
            "price": 5.00,
            "expiration_days": 30,
            "platform_prices": {
                "stripe": {
                    "product_id": "prod_RsSg8XuYBgOyZn",
                    "price_id": "price_1QyhlMF8KEZSCnqO103BMBHF",
                    "amount": 500,
                },
                "apple": {
                    "product_id": "com.yourdomain.credits.100",
                    "price_id": "333_credits_tier1",
                },
                "google": {"product_id": "credits_333", "price_id": "credits_333_sku"},
            },
            "is_subscription": False,
        },
        {
            "name": "667 Credits",
            "credits": 667,
            "price": 10.00,
            "expiration_days": 60,
            "platform_prices": {
                "stripe": {
                    "product_id": "prod_RsSjKF7Hed1Sam",
                    "price_id": "price_1QyhnnF8KEZSCnqOM7rjUBbi",
                    "amount": 1000,
                },
                "apple": {
                    "product_id": "com.yourdomain.credits.500",
                    "price_id": "667_credits_tier2",
                },
                "google": {"product_id": "credits_667", "price_id": "credits_667_sku"},
            },
            "is_subscription": False,
        },
        {
            "name": "1333 Credits",
            "credits": 1333,
            "price": 20.00,
            "expiration_days": 60,
            "platform_prices": {
                "stripe": {
                    "product_id": "prod_RsSkJUEskVEyZg",
                    "price_id": "price_1QyhovF8KEZSCnqOApeGFc9v",
                    "amount": 2000,
                },
                "apple": {
                    "product_id": "com.yourdomain.credits.1000",
                    "price_id": "1333_credits_tier3",
                },
                "google": {
                    "product_id": "credits_1333",
                    "price_id": "credits_1333_sku",
                },
            },
            "is_subscription": False,
        },
    ],
    "subscription": [
        {
            "name": "Gold",
            "credits": 800,
            "price": 10.00,
            "expiration_days": 90,
            "platform_prices": {
                "stripe": {
                    "product_id": "prod_RsbjJC0GLvf99b",
                    "price_id": "price_1QyqVkF8KEZSCnqOKQsqluaN",
                    "amount": 1000,
                },
                "apple": {
                    "product_id": "com.yourdomain.sub.monthly",
                    "price_id": "monthly_sub_tier1",
                },
                "google": {"product_id": "sub_monthly", "price_id": "sub_monthly_sku"},
            },
            "is_subscription": True,
            "subscription_period": SubscriptionPeriod.MONTHLY,
        },
        {
            "name": "Gold",
            "credits": 800,
            "price": 100.00,
            "expiration_days": 90,
            "platform_prices": {
                "stripe": {
                    "product_id": "prod_Rssr47bE7dsh7j",
                    "price_id": "price_1Qz75cF8KEZSCnqOgNueVI2I",
                    "amount": 10000,
                },
                "apple": {
                    "product_id": "com.yourdomain.sub.yearly",
                    "price_id": "yearly_sub_tier1",
                },
                "google": {"product_id": "sub_yearly", "price_id": "sub_yearly_sku"},
            },
            "is_subscription": True,
            "subscription_period": SubscriptionPeriod.YEARLY,
        },
        {
            "name": "Platinum",
            "credits": 2500,
            "price": 30.00,
            "expiration_days": 90,
            "platform_prices": {
                "stripe": {
                    "product_id": "prod_RsbjU4VPIHRpix",
                    "price_id": "price_1QyqWSF8KEZSCnqOLR3IzO7J",
                    "amount": 3000,
                },
                "apple": {
                    "product_id": "com.yourdomain.sub.monthly",
                    "price_id": "monthly_sub_tier1",
                },
                "google": {"product_id": "sub_monthly", "price_id": "sub_monthly_sku"},
            },
            "is_subscription": True,
            "subscription_period": SubscriptionPeriod.MONTHLY,
        },
        {
            "name": "Platinum",
            "credits": 2500,
            "price": 300.00,
            "expiration_days": 90,
            "platform_prices": {
                "stripe": {
                    "product_id": "prod_RssteGejw19lTo",
                    "price_id": "price_1Qz77iF8KEZSCnqOI1HHn7QO",
                    "amount": 30000,
                },
                "apple": {
                    "product_id": "com.yourdomain.sub.yearly",
                    "price_id": "yearly_sub_tier1",
                },
                "google": {"product_id": "sub_yearly", "price_id": "sub_yearly_sku"},
            },
            "is_subscription": True,
            "subscription_period": SubscriptionPeriod.YEARLY,
        },
    ],
}


CREDIT_PACKAGES_PROD = {
    "pay_as_you_go": [
        {
            "name": "333 Credits",
            "credits": 333,
            "price": 5.00,
            "expiration_days": 30,
            "platform_prices": {
                "stripe": {
                    "product_id": "prod_RuPOOxLHDdw3wI",
                    "price_id": "price_1R0aa8F8KEZSCnqOjhGBdyDK",
                    "amount": 500,
                },
                "apple": {
                    "product_id": "com.yourdomain.credits.100",
                    "price_id": "333_credits_tier1",
                },
                "google": {"product_id": "credits_333", "price_id": "credits_333_sku"},
            },
            "is_subscription": False,
        },
        {
            "name": "667 Credits",
            "credits": 667,
            "price": 10.00,
            "expiration_days": 60,
            "platform_prices": {
                "stripe": {
                    "product_id": "prod_RuPQf8fQQJvCf9",
                    "price_id": "price_1R0abCF8KEZSCnqOqjfgDFUO",
                    "amount": 1000,
                },
                "apple": {
                    "product_id": "com.yourdomain.credits.500",
                    "price_id": "667_credits_tier2",
                },
                "google": {"product_id": "credits_667", "price_id": "credits_667_sku"},
            },
            "is_subscription": False,
        },
        {
            "name": "1333 Credits",
            "credits": 1333,
            "price": 20.00,
            "expiration_days": 60,
            "platform_prices": {
                "stripe": {
                    "product_id": "prod_RuPQmHSn7m5Qyq",
                    "price_id": "price_1R0abwF8KEZSCnqOzKuhGO70",
                    "amount": 2000,
                },
                "apple": {
                    "product_id": "com.yourdomain.credits.1000",
                    "price_id": "1333_credits_tier3",
                },
                "google": {
                    "product_id": "credits_1333",
                    "price_id": "credits_1333_sku",
                },
            },
            "is_subscription": False,
        },
    ],
    "subscription": [
        {
            "name": "Gold",
            "credits": 800,
            "price": 10.00,
            "expiration_days": 90,
            "platform_prices": {
                "stripe": {
                    "product_id": "prod_RuPRsWwvLkAhbe",
                    "price_id": "price_1R0ad3F8KEZSCnqOSNmp7cpo",
                    "amount": 1000,
                },
                "apple": {
                    "product_id": "com.yourdomain.sub.monthly",
                    "price_id": "monthly_sub_tier1",
                },
                "google": {"product_id": "sub_monthly", "price_id": "sub_monthly_sku"},
            },
            "is_subscription": True,
            "subscription_period": SubscriptionPeriod.MONTHLY,
        },
        {
            "name": "Gold",
            "credits": 800,
            "price": 100.00,
            "expiration_days": 90,
            "platform_prices": {
                "stripe": {
                    "product_id": "prod_RuPS4iOZ1MUMsE",
                    "price_id": "price_1R0adwF8KEZSCnqObLrtQ7JG",
                    "amount": 10000,
                },
                "apple": {
                    "product_id": "com.yourdomain.sub.yearly",
                    "price_id": "yearly_sub_tier1",
                },
                "google": {"product_id": "sub_yearly", "price_id": "sub_yearly_sku"},
            },
            "is_subscription": True,
            "subscription_period": SubscriptionPeriod.YEARLY,
        },
        {
            "name": "Platinum",
            "credits": 2500,
            "price": 30.00,
            "expiration_days": 90,
            "platform_prices": {
                "stripe": {
                    "product_id": "prod_RuPT6johT6UCX6",
                    "price_id": "price_1R0aeiF8KEZSCnqOp0hlEZk8",
                    "amount": 3000,
                },
                "apple": {
                    "product_id": "com.yourdomain.sub.monthly",
                    "price_id": "monthly_sub_tier1",
                },
                "google": {"product_id": "sub_monthly", "price_id": "sub_monthly_sku"},
            },
            "is_subscription": True,
            "subscription_period": SubscriptionPeriod.MONTHLY,
        },
        {
            "name": "Platinum",
            "credits": 2500,
            "price": 300.00,
            "expiration_days": 90,
            "platform_prices": {
                "stripe": {
                    "product_id": "prod_RuPUdEc5Eznx56",
                    "price_id": "price_1R0afQF8KEZSCnqOmYdclkCB",
                    "amount": 30000,
                },
                "apple": {
                    "product_id": "com.yourdomain.sub.yearly",
                    "price_id": "yearly_sub_tier1",
                },
                "google": {"product_id": "sub_yearly", "price_id": "sub_yearly_sku"},
            },
            "is_subscription": True,
            "subscription_period": SubscriptionPeriod.YEARLY,
        },
    ],
}


class CreditPackageService:
    def __init__(
        self,
        session: AsyncSession = Depends(db_session),
    ) -> None:
        self.session = session

    async def seed_credit_packages(self) -> bool:
        """Seed credit packages with prices for all platforms"""
        try:
            # First, delete all existing packages
            delete_query = delete(CreditPackage)
            await self.session.execute(delete_query)

            package_list = CREDIT_PACKAGES

            if settings.APP_ENV == "production" or settings.APP_ENV == "rc":
                package_list = CREDIT_PACKAGES_PROD

            # Insert new packages
            for package_type, packages in package_list.items():
                for package_data in packages:
                    # Extract platform-specific IDs
                    stripe_data = package_data["platform_prices"].get("stripe", {})
                    apple_data = package_data["platform_prices"].get("apple", {})
                    google_data = package_data["platform_prices"].get("google", {})

                    # Create package with all required fields
                    package = CreditPackage(
                        name=package_data["name"],
                        credits=package_data["credits"],
                        price=package_data["price"],  # Set the default price
                        expiration_days=package_data["expiration_days"],
                        is_subscription=package_data["is_subscription"],
                        subscription_period=package_data.get("subscription_period"),
                        # Platform-specific IDs
                        stripe_product_id=stripe_data.get("product_id"),
                        stripe_price_id=stripe_data.get("price_id"),
                        apple_product_id=apple_data.get("product_id"),
                        google_product_id=google_data.get("product_id"),
                        # Store full platform price data
                        platform_metadata={
                            "platform_prices": package_data["platform_prices"]
                        },
                    )
                    self.session.add(package)

            await self.session.commit()
            return True

        except Exception as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=500, detail=f"Failed to seed credit packages: {str(e)}"
            )

    async def list_packages(
        self, is_subscription: Optional[bool] = None, platform: Optional[str] = None
    ) -> List[Dict]:
        """
        List credit packages with optional filtering by subscription type and platform
        """
        query = select(CreditPackage)
        if is_subscription is not None:
            query = query.where(CreditPackage.is_subscription == is_subscription)

        result = await self.session.execute(query)
        packages = result.scalars().all()

        # Format response based on platform if specified
        formatted_packages = []
        for package in packages:
            package_dict = {
                "id": str(package.id),
                "name": package.name,
                "credits": package.credits,
                "price": package.price,
                "is_subscription": package.is_subscription,
                "subscription_period": package.subscription_period,
                "expiration_days": package.expiration_days,
            }

            if platform:
                # Add platform-specific pricing info
                platform_prices = package.platform_metadata.get(
                    "platform_prices", {}
                ).get(platform, {})
                package_dict.update(
                    {
                        f"{platform}_product_id": platform_prices.get("product_id"),
                        f"{platform}_price_id": platform_prices.get("price_id"),
                        "price_amount": platform_prices.get("amount"),
                    }
                )
            else:
                # Include all platform data
                package_dict["platform_prices"] = package.platform_metadata.get(
                    "platform_prices", {}
                )

            formatted_packages.append(package_dict)

        return formatted_packages

    async def get_package_by_id(
        self, package_id: str, platform: Optional[str] = None
    ) -> Dict:
        """
        Get a specific package by ID with optional platform-specific formatting
        """
        query = select(CreditPackage).where(CreditPackage.id == package_id)
        result = await self.session.execute(query)
        package = result.scalars().first()

        if not package:
            raise HTTPException(status_code=404, detail="Credit package not found")

        # Format response
        package_dict = {
            "id": str(package.id),
            "name": package.name,
            "credits": package.credits,
            "price": package.price,
            "is_subscription": package.is_subscription,
            "subscription_period": package.subscription_period,
        }

        if platform:
            # Add platform-specific pricing info
            platform_prices = package.platform_metadata.get("platform_prices", {}).get(
                platform, {}
            )
            package_dict.update(
                {
                    f"{platform}_product_id": platform_prices.get("product_id"),
                    f"{platform}_price_id": platform_prices.get("price_id"),
                    "price_amount": platform_prices.get("amount"),
                }
            )
        else:
            # Include all platform data
            package_dict["platform_prices"] = package.platform_metadata.get(
                "platform_prices", {}
            )

        return package_dict

    async def get_package_by_platform_id(self, platform: str, product_id: str) -> Dict:
        """
        Get a package by its platform-specific product ID
        """
        query = select(CreditPackage)
        result = await self.session.execute(query)
        packages = result.scalars().all()

        for package in packages:
            platform_prices = package.platform_metadata.get("platform_prices", {}).get(
                platform, {}
            )
            if platform_prices.get("product_id") == product_id:
                return {
                    "id": str(package.id),
                    "name": package.name,
                    "credits": package.credits,
                    "price": package.price,
                    "is_subscription": package.is_subscription,
                    "subscription_period": package.subscription_period,
                    f"{platform}_product_id": platform_prices.get("product_id"),
                    f"{platform}_price_id": platform_prices.get("price_id"),
                    "price_amount": platform_prices.get("amount"),
                }

        raise HTTPException(
            status_code=404,
            detail=f"Credit package not found for {platform} product ID: {product_id}",
        )

    async def update_package(self, package_id: str, update_data: Dict) -> Dict:
        """
        Update a credit package
        """
        query = select(CreditPackage).where(CreditPackage.id == package_id)
        result = await self.session.execute(query)
        package = result.scalars().first()

        if not package:
            raise HTTPException(status_code=404, detail="Credit package not found")

        try:
            # Update basic fields
            for field in [
                "name",
                "credits",
                "price",
                "is_subscription",
                "subscription_period",
            ]:
                if field in update_data:
                    setattr(package, field, update_data[field])

            # Update platform-specific data
            if "platform_prices" in update_data:
                current_metadata = package.platform_metadata or {}
                current_metadata["platform_prices"] = update_data["platform_prices"]
                package.platform_metadata = current_metadata

                # Update individual platform IDs
                for platform, data in update_data["platform_prices"].items():
                    if platform == "stripe":
                        package.stripe_product_id = data.get("product_id")
                        package.stripe_price_id = data.get("price_id")
                    elif platform == "apple":
                        package.apple_product_id = data.get("product_id")
                    elif platform == "google":
                        package.google_product_id = data.get("product_id")

            await self.session.commit()
            return await self.get_package_by_id(package_id)

        except Exception as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=500, detail=f"Failed to update credit package: {str(e)}"
            )
