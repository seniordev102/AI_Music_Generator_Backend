import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, NamedTuple, Optional, Tuple
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import and_, case, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.http_response_model import PageMeta
from app.database import db_session
from app.models import (
    CreditConsumptionLog,
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


class CreditManagementService:
    def __init__(
        self,
        session: AsyncSession = Depends(db_session),
    ) -> None:
        self.session = session

    async def _get_user_by_email(self, email: str) -> User:
        """Get user by email or raise HTTPException if not found"""
        query = select(User).where(User.email == email)
        result = await self.session.execute(query)
        user = result.scalars().first()

        if not user:
            raise HTTPException(
                status_code=404, detail=f"User with email {email} not found"
            )

        return user

    async def _get_package_by_id(self, package_id: str) -> CreditPackage:
        """Get credit package by ID"""
        query = select(CreditPackage).where(CreditPackage.id == package_id)
        result = await self.session.execute(query)
        package = result.scalars().first()

        if not package:
            raise HTTPException(
                status_code=404, detail=f"Credit package with ID {package_id} not found"
            )

        return package

    async def _get_signup_bonus_package(self) -> CreditPackage:
        """Get the 333 Credits package for signup bonuses"""
        query = (
            select(CreditPackage).where(CreditPackage.is_subscription == False).limit(1)
        )
        result = await self.session.execute(query)
        package = result.scalar_one_or_none()
        return package

    async def _get_active_credit_balances(self, user_id: UUID, current_time: datetime):
        """Get all active credit balances for a user"""
        query = (
            select(UserCreditBalance)
            .where(
                and_(
                    UserCreditBalance.user_id == user_id,
                    UserCreditBalance.is_active == True,
                    UserCreditBalance.remaining_amount > 0,
                    or_(
                        UserCreditBalance.expires_at > current_time,
                        UserCreditBalance.expires_at == None,
                    ),
                )
            )
            .order_by(
                case((UserCreditBalance.expires_at == None, 1), else_=0),
                UserCreditBalance.expires_at,
            )
        )

        result = await self.session.execute(query)
        return result.scalars().all()

    async def _get_or_create_balance(self, email: str) -> Dict:
        """Get aggregated balance information for a user"""
        current_time = datetime.now(timezone.utc)
        user = await self._get_user_by_email(email)
        balances = await self._get_active_credit_balances(user.id, current_time)

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

    def _format_subscription_details(
        self, sub_with_package: Optional[SubscriptionWithPackage]
    ) -> Optional[Dict]:
        """Format subscription and package details into a dictionary"""
        if not sub_with_package:
            return None

        subscription = sub_with_package.subscription
        package = sub_with_package.package

        return {
            "id": str(subscription.id),
            "package_name": package.name,
            "credits_per_period": subscription.credits_per_period,
            "current_period_end": subscription.current_period_end,
            "status": subscription.status,
            "platform": subscription.platform,
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "package_details": {
                "id": str(package.id),
                "name": package.name,
                "credits": package.credits,
                "price": package.price,
                "subscription_period": package.subscription_period,
                "is_subscription": package.is_subscription,
            },
        }

    async def _get_active_subscription(
        self, email: str
    ) -> Optional[SubscriptionWithPackage]:
        """Get user's active subscription with package details"""
        user = await self._get_user_by_email(email)

        query = (
            select(UserSubscription, CreditPackage)
            .join(CreditPackage, UserSubscription.package_id == CreditPackage.id)
            .where(
                and_(
                    UserSubscription.user_id == user.id,
                    UserSubscription.status == "active",
                    UserSubscription.current_period_end > datetime.now(timezone.utc),
                )
            )
        )
        result = await self.session.execute(query)
        row = result.first()

        if row:
            subscription, package = row
            return SubscriptionWithPackage(subscription=subscription, package=package)
        return None

    async def get_user_credit_details(
        self, email: str, at_timestamp: Optional[datetime] = None
    ) -> Dict:
        user = await self._get_user_by_email(email=email)
        current_time = datetime.now(timezone.utc)

        # Get all active credit balances and their associated packages
        query = (
            select(UserCreditBalance, CreditPackage)
            .outerjoin(CreditPackage, UserCreditBalance.package_id == CreditPackage.id)
            .where(
                and_(
                    UserCreditBalance.user_id == user.id,
                    UserCreditBalance.remaining_amount > 0,
                    UserCreditBalance.is_active == True,
                    or_(
                        UserCreditBalance.expires_at > current_time,
                        UserCreditBalance.expires_at == None,
                    ),
                )
            )
            .order_by(UserCreditBalance.expires_at.asc().nullslast())
        )

        result = await self.session.execute(query)
        balances_with_packages = result.all()

        total_current_balance = 0
        total_credits_earned = 0
        total_credits_used = 0
        balance_details = []

        for balance, package in balances_with_packages:
            total_current_balance += balance.remaining_amount
            total_credits_earned += balance.initial_amount
            total_credits_used += balance.initial_amount - balance.remaining_amount

            time_to_expiry = None
            if balance.expires_at:
                remaining_time = balance.expires_at - current_time
                days = remaining_time.days
                hours = remaining_time.seconds // 3600
                minutes = (remaining_time.seconds % 3600) // 60

                time_to_expiry = {
                    "days": max(0, days),
                    "hours": hours,
                    "minutes": minutes,
                    "total_seconds": max(0, int(remaining_time.total_seconds())),
                }

            balance_details.append(
                {
                    "balance_id": str(balance.id),
                    "package_name": package.name if package else "System Credit",
                    "package_id": str(package.id) if package else None,
                    "initial_amount": balance.initial_amount,
                    "remaining_amount": balance.remaining_amount,
                    "expires_at": (
                        balance.expires_at.isoformat() if balance.expires_at else None
                    ),
                    "time_to_expiry": time_to_expiry,
                    "consumed_percentage": round(
                        (
                            (balance.initial_amount - balance.remaining_amount)
                            / balance.initial_amount
                        )
                        * 100,
                        2,
                    ),
                    "created_at": balance.created_at.isoformat(),
                }
            )

        subscription_with_package = await self._get_active_subscription(email)
        subscription_details = self._format_subscription_details(
            subscription_with_package
        )

        return {
            "current_balance": total_current_balance,
            "total_credits_earned": total_credits_earned,
            "total_credits_used": total_credits_used,
            "last_updated": current_time,
            "balance_details": balance_details,
            "active_subscription": subscription_details,
        }

    def _format_transaction_details(
        self, tx_with_package: TransactionWithPackage
    ) -> Dict:
        """Format transaction and package details into a dictionary"""
        transaction = tx_with_package.transaction
        package = tx_with_package.package

        tx_dict = {
            "id": str(transaction.id),
            "transaction_type": transaction.transaction_type,
            "transaction_source": transaction.transaction_source,
            "amount": transaction.amount,
            "balance_after": transaction.balance_after,
            "description": transaction.description,
            "created_at": transaction.created_at,
            "package_details": None,
        }

        if package:
            tx_dict["package_details"] = {
                "id": str(package.id),
                "name": package.name,
                "credits": package.credits,
                "is_subscription": package.is_subscription,
            }

        return tx_dict

    async def get_transaction_history(
        self,
        user_email: str,
        page: int = 1,
        page_size: int = 20,
        tx_type: Optional[TransactionType] = None,
        source: Optional[TransactionSource] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Tuple[List[Dict], Dict]:
        """Get paginated transaction history with filters"""
        user = await self._get_user_by_email(email=user_email)

        query = (
            select(CreditTransaction, CreditPackage)
            .outerjoin(CreditPackage, CreditTransaction.package_id == CreditPackage.id)
            .where(CreditTransaction.user_id == user.id)
        )

        if tx_type:
            query = query.where(CreditTransaction.transaction_type == tx_type)
        if source:
            query = query.where(CreditTransaction.transaction_source == source)
        if start_date:
            query = query.where(CreditTransaction.created_at >= start_date)
        if end_date:
            query = query.where(CreditTransaction.created_at <= end_date)

        query = query.order_by(CreditTransaction.created_at.desc())

        # Execute count query
        count_query = select(func.count()).select_from(query.subquery())
        total_count = await self.session.scalar(count_query)

        # Add pagination
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)

        transactions = []
        for row in result:
            tx_with_package = TransactionWithPackage(transaction=row[0], package=row[1])
            transactions.append(self._format_transaction_details(tx_with_package))

        total_pages = (total_count + page_size - 1) // page_size
        pagination = PageMeta(
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            total_items=total_count,
        )

        return transactions, pagination

    async def get_transaction_analytics(
        self, user_email: str, time_range: Optional[timedelta] = None
    ) -> Dict:
        """Get transaction analytics for specified time range"""
        user = await self._get_user_by_email(user_email)
        now = datetime.now(timezone.utc)
        start_time = now - (time_range or timedelta(days=30))

        # Get current balance details
        balance_info = await self._get_or_create_balance(user_email)

        # Aggregate by transaction type
        type_stats = {}
        for tx_type in TransactionType:
            query = select(
                func.count().label("count"),
                func.sum(CreditTransaction.amount).label("total_amount"),
            ).where(
                and_(
                    CreditTransaction.transaction_type == tx_type,
                    CreditTransaction.created_at
                    >= start_time.replace(
                        tzinfo=None
                    ),  # Remove timezone for comparison
                    CreditTransaction.user_id == str(user.id),
                )
            )
            result = await self.session.execute(query)
            row = result.first()
            type_stats[tx_type] = {
                "count": row.count,
                "total_amount": row.total_amount or 0,
            }

        # Aggregate by source
        source_stats = {}
        for source in TransactionSource:
            query = select(
                func.count().label("count"),
                func.sum(CreditTransaction.amount).label("total_amount"),
            ).where(
                and_(
                    CreditTransaction.transaction_source == source,
                    CreditTransaction.created_at
                    >= start_time.replace(
                        tzinfo=None
                    ),  # Remove timezone for comparison
                    CreditTransaction.user_id == str(user.id),
                )
            )
            result = await self.session.execute(query)
            row = result.first()
            source_stats[source] = {
                "count": row.count,
                "total_amount": row.total_amount or 0,
            }

        # Calculate daily trends with timezone handling
        daily_query = (
            select(
                func.date_trunc("day", CreditTransaction.created_at).label("day"),
                func.sum(
                    case(
                        (
                            CreditTransaction.transaction_type == TransactionType.DEBIT,
                            CreditTransaction.amount,
                        ),
                        else_=0,
                    )
                ).label("debit_amount"),
                func.sum(
                    case(
                        (
                            CreditTransaction.transaction_type
                            == TransactionType.CREDIT,
                            CreditTransaction.amount,
                        ),
                        else_=0,
                    )
                ).label("credit_amount"),
            )
            .where(
                and_(
                    CreditTransaction.user_id == str(user.id),
                    CreditTransaction.created_at
                    >= start_time.replace(
                        tzinfo=None
                    ),  # Remove timezone for comparison
                )
            )
            .group_by(text("day"))
            .order_by(text("day"))
        )

        result = await self.session.execute(daily_query)
        daily_trends = [
            {
                "date": row.day.replace(
                    tzinfo=timezone.utc
                ),  # Add UTC timezone to result
                "debit_amount": row.debit_amount or 0,
                "credit_amount": row.credit_amount or 0,
            }
            for row in result
        ]

        days_in_period = (now - start_time).days
        debit_count = type_stats[TransactionType.DEBIT]["count"]
        debit_total = type_stats[TransactionType.DEBIT]["total_amount"]

        return {
            "current_balance": balance_info["current_balance"],
            "period_stats": {
                "start_date": start_time,
                "end_date": now,
                "days_in_period": days_in_period,
            },
            "transaction_types": type_stats,
            "sources": source_stats,
            "daily_trends": daily_trends,
            "averages": {
                "daily_usage": debit_total / max(1, days_in_period),
                "credits_per_transaction": debit_total / max(1, debit_count),
            },
        }

    async def add_credits(
        self,
        user_email: str,
        package_id: str,
        source: TransactionSource,
        platform_transaction_id: Optional[str] = None,
        subscription_id: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict:
        """Add credits to a user's account"""
        user = await self._get_user_by_email(email=user_email)
        current_time = datetime.now(timezone.utc)

        # Get package details if provided
        package = None
        amount = 0
        expiration_date = None

        if package_id:
            try:
                package = await self._get_package_by_id(package_id=package_id)
                amount = package.credits

                # Calculate expiration if applicable
                if package.expiration_days:
                    expiration_date = current_time + timedelta(
                        days=package.expiration_days
                    )
            except HTTPException:
                # If package not found, use the 333 Credits package
                package = await self._get_signup_bonus_package()
                package_id = str(package.id)
                # Amount must be provided in metadata in this case
                amount = metadata.get("amount", 0) if metadata else 0
        else:
            # If no package_id provided, use the 333 Credits package
            package = await self._get_signup_bonus_package()
            package_id = str(package.id)
            # Amount must be provided in metadata in this case
            amount = metadata.get("amount", 0) if metadata else 0

        try:
            # Calculate current balance by summing all active balances
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
            result = await self.session.execute(current_balance_query)
            current_balance = result.scalar() or 0
            new_balance = current_balance + amount

            # Create credit transaction with balance_after
            transaction = CreditTransaction(
                user_id=str(user.id),
                transaction_type=TransactionType.CREDIT,
                transaction_source=source,
                amount=amount,
                balance_after=new_balance,  # Set the balance_after field
                description=description or f"Credits added via {source.value}",
                platform_transaction_id=platform_transaction_id,
                subscription_id=subscription_id,
                package_id=package_id,
                credit_metadata=metadata or {},
            )
            self.session.add(transaction)
            await self.session.flush()  # Get transaction ID

            # Create credit balance record with expiration
            credit_balance = UserCreditBalance(
                user_id=user.id,
                package_id=UUID(package_id) if package_id else None,
                transaction_id=transaction.id,
                initial_amount=amount,
                remaining_amount=amount,
                expires_at=expiration_date,
                is_active=True,
            )
            self.session.add(credit_balance)

            await self.session.commit()
            return {
                "transaction_id": str(transaction.id),
                "amount": amount,
                "new_balance": new_balance,
                "expires_at": expiration_date.isoformat() if expiration_date else None,
                "source": source,
                "platform_transaction_id": platform_transaction_id,
                "subscription_id": subscription_id,
                "package_id": package_id,
            }

        except Exception as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=500, detail=f"Failed to add credits: {str(e)}"
            )

    async def deduct_credits(
        self,
        user_email: str,
        amount: int,
        api_endpoint: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict:
        """Deduct credits from user balance using FIFO based on expiration"""
        if amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Deduction amount must be positive",
            )

        user = await self._get_user_by_email(user_email)
        current_time = datetime.now(timezone.utc)

        # Get active credit balances ordered by expiration date (FIFO)
        balances = await self._get_active_credit_balances(user.id, current_time)

        total_available = sum(balance.remaining_amount for balance in balances)
        if total_available < amount:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Insufficient credits. Please recharge your account",
            )

        try:
            remaining_deduction = amount
            consumption_logs = []
            final_balance_after = total_available - amount

            # Deduct credits from balances in FIFO order
            for balance in balances:
                if remaining_deduction <= 0:
                    break

                deduction_amount = min(remaining_deduction, balance.remaining_amount)
                balance.remaining_amount -= deduction_amount
                remaining_deduction -= deduction_amount

                if balance.remaining_amount == 0:
                    balance.consumed_at = current_time
                    balance.is_active = False

                # Log consumption
                consumption_log = CreditConsumptionLog(
                    user_id=user.id,
                    balance_id=balance.id,
                    transaction_id=balance.transaction_id,
                    amount=deduction_amount,
                    api_endpoint=api_endpoint,
                    metadata=metadata or {},
                )
                consumption_logs.append(consumption_log)

            # Create debit transaction
            transaction = CreditTransaction(
                user_id=str(user.id),
                transaction_type=TransactionType.DEBIT,
                transaction_source=TransactionSource.API_USAGE,
                amount=amount,
                balance_after=final_balance_after,
                description=description or f"API usage: {api_endpoint}",
                api_endpoint=api_endpoint,
                credit_metadata=metadata or {},
            )

            self.session.add(transaction)
            for log in consumption_logs:
                self.session.add(log)

            await self.session.commit()

            return {
                "transaction_id": str(transaction.id),
                "amount": amount,
                "new_balance": final_balance_after,
                "timestamp": transaction.created_at,
                "api_endpoint": api_endpoint,
            }

        except Exception as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to deduct credits: {str(e)}",
            )

    async def transfer_credits(
        self,
        from_email: str,
        to_email: str,
        amount: int,
        description: Optional[str] = None,
    ) -> Dict:
        """Transfer credits between users using FIFO consumption"""
        if amount <= 0:
            raise HTTPException(
                status_code=400, detail="Transfer amount must be positive"
            )

        if from_email.lower() == to_email.lower():
            raise HTTPException(
                status_code=400, detail="Cannot transfer credits to yourself"
            )

        # Validate transfer request and get user details
        from_user = await self._get_user_by_email(from_email)
        to_user = await self._get_user_by_email(to_email)
        current_time = datetime.now(timezone.utc)

        # Get sender's available balances
        sender_balances = await self._get_active_credit_balances(
            from_user.id, current_time
        )
        total_available = sum(balance.remaining_amount for balance in sender_balances)

        if total_available < amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient credits for transfer",
            )

        try:
            transfer_id = uuid.uuid4()
            remaining_transfer = amount
            consumption_logs = []
            final_sender_balance = total_available - amount

            # Deduct from sender's balances in FIFO order
            for balance in sender_balances:
                if remaining_transfer <= 0:
                    break

                deduction_amount = min(remaining_transfer, balance.remaining_amount)
                balance.remaining_amount -= deduction_amount
                remaining_transfer -= deduction_amount

                if balance.remaining_amount == 0:
                    balance.consumed_at = current_time
                    balance.is_active = False

                # Log consumption
                consumption_log = CreditConsumptionLog(
                    user_id=from_user.id,
                    balance_id=balance.id,
                    transaction_id=balance.transaction_id,
                    amount=deduction_amount,
                    metadata={
                        "transfer_id": str(transfer_id),
                        "recipient_email": to_email,
                    },
                )
                consumption_logs.append(consumption_log)

            # Calculate receiver's new balance
            receiver_current_balance_query = select(
                func.sum(UserCreditBalance.remaining_amount)
            ).where(
                and_(
                    UserCreditBalance.user_id == to_user.id,
                    UserCreditBalance.is_active == True,
                    or_(
                        UserCreditBalance.expires_at > current_time,
                        UserCreditBalance.expires_at == None,
                    ),
                )
            )
            result = await self.session.execute(receiver_current_balance_query)
            receiver_current_balance = result.scalar() or 0
            receiver_new_balance = receiver_current_balance + amount

            # Get the first available package_id from sender's balances
            transfer_package_id = next(
                (
                    str(balance.package_id)
                    for balance in sender_balances
                    if balance.package_id
                ),
                None,
            )

            # If no package_id is available, use the 333 Credits package
            if not transfer_package_id:
                signup_package = await self._get_signup_bonus_package()
                transfer_package_id = str(signup_package.id)

            # Create sender's debit transaction
            sender_tx = CreditTransaction(
                user_id=str(from_user.id),
                transaction_type=TransactionType.DEBIT,
                transaction_source=TransactionSource.P2P_TRANSFER,
                amount=amount,
                balance_after=final_sender_balance,
                description=description or f"Transfer to {to_user.email}",
                related_transaction_id=transfer_id,
                package_id=transfer_package_id,
                credit_metadata={
                    "transfer_id": str(transfer_id),
                    "recipient_email": to_email,
                    "transfer_time": current_time.isoformat(),
                },
            )
            self.session.add(sender_tx)

            # Create recipient's credit balance
            recipient_balance = UserCreditBalance(
                user_id=to_user.id,
                package_id=UUID(transfer_package_id) if transfer_package_id else None,
                transaction_id=transfer_id,
                initial_amount=amount,
                remaining_amount=amount,
                expires_at=None,  # Transferred credits don't expire
                is_active=True,
            )
            self.session.add(recipient_balance)

            # Create recipient's credit transaction
            receiver_tx = CreditTransaction(
                user_id=to_user.id,
                transaction_type=TransactionType.CREDIT,
                transaction_source=TransactionSource.P2P_TRANSFER,
                amount=amount,
                balance_after=receiver_new_balance,
                description=description or f"Transfer from {from_user.email}",
                related_transaction_id=transfer_id,
                package_id=transfer_package_id,
                credit_metadata={
                    "transfer_id": str(transfer_id),
                    "sender_email": from_email,
                    "transfer_time": current_time.isoformat(),
                },
            )
            self.session.add(receiver_tx)

            # Add all consumption logs
            for log in consumption_logs:
                self.session.add(log)

            await self.session.commit()

            return {
                "transfer_id": str(transfer_id),
                "amount": amount,
                "timestamp": current_time,
                "sender": {
                    "email": from_email,
                    "new_balance": final_sender_balance,
                    "transaction_id": str(sender_tx.id),
                },
                "recipient": {
                    "email": to_email,
                    "new_balance": receiver_new_balance,
                    "transaction_id": str(receiver_tx.id),
                },
            }

        except Exception as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Transfer failed: {str(e)}",
            )

    async def process_subscription_renewal(
        self, user_email: str, subscription_id: str
    ) -> Dict:
        """Process subscription renewal and add credits"""
        user = await self._get_user_by_email(user_email)
        current_time = datetime.now(timezone.utc)

        # Get subscription
        query = select(UserSubscription).where(
            and_(
                UserSubscription.id == subscription_id,
                UserSubscription.user_id == str(user.id),
                UserSubscription.status == "active",
            )
        )
        result = await self.session.execute(query)
        subscription = result.scalars().first()

        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Active subscription not found",
            )

        try:
            # Get the subscription package details
            package = await self._get_package_by_id(str(subscription.package_id))
            expiration_date = None
            if package.expiration_days:
                expiration_date = current_time + timedelta(days=package.expiration_days)

            # Add credits for the new period
            result = await self.add_credits(
                user_email=user_email,
                source=TransactionSource.SUBSCRIPTION_RENEWAL,
                subscription_id=subscription_id,
                package_id=str(package.id),
                description=f"Subscription renewal credits ({subscription.platform})",
                metadata={
                    "subscription_id": subscription_id,
                    "platform": subscription.platform,
                    "renewal_period_start": subscription.current_period_start.isoformat(),
                    "renewal_period_end": subscription.current_period_end.isoformat(),
                    "expires_at": (
                        expiration_date.isoformat() if expiration_date else None
                    ),
                },
            )

            return {
                "subscription_id": subscription_id,
                "credits_added": subscription.credits_per_period,
                "transaction_id": result["transaction_id"],
                "expires_at": result["expires_at"],
                "timestamp": current_time.isoformat(),
            }

        except Exception as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process subscription renewal: {str(e)}",
            )

    async def validate_transfer_request(
        self, user_email: str, receiver_email: str, amount: int
    ):
        sender_user = await self._get_user_by_email(email=user_email)

        if not sender_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"You don't have access to transfer credit",
            )

        receiver_user = await self._get_user_by_email(email=receiver_email)

        if not receiver_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"We can not find the beneficiary account {receiver_email}",
            )

        # check sender user have credit balance to execute the transaction
        sender_balance = await self.get_user_credit_details(email=user_email)

        if int(sender_balance.get("current_balance")) < amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"You don't have enough fund to execute this transaction",
            )

        return {
            "beneficiary_name": receiver_user.name,
            "beneficiary_email": receiver_user.email,
            "beneficiary_profile_image": receiver_user.profile_image,
        }

    async def get_subscription_details(self, email: str) -> Optional[Dict]:
        try:
            # Get user's active subscription with package details
            subscription_with_package = await self._get_active_subscription(email)

            if not subscription_with_package:
                return None

            subscription = subscription_with_package.subscription
            package = subscription_with_package.package

            # Calculate remaining time in current period
            now = datetime.now(timezone.utc)
            remaining_time = subscription.current_period_end - now
            days = remaining_time.days
            hours = remaining_time.seconds // 3600
            minutes = (remaining_time.seconds % 3600) // 60

            return {
                "id": str(subscription.id),
                "package_name": package.name,
                "credits_per_period": subscription.credits_per_period,
                "current_period_start": subscription.current_period_start,
                "current_period_end": subscription.current_period_end,
                "time_remaining": {
                    "days": max(0, days),
                    "hours": hours,
                    "minutes": minutes,
                    "total_seconds": max(0, int(remaining_time.total_seconds())),
                },
                "status": subscription.status,
                "platform": subscription.platform,
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "package_details": {
                    "id": str(package.id),
                    "name": package.name,
                    "credits": package.credits,
                    "price": package.price,
                    "subscription_period": package.subscription_period,
                    "is_subscription": package.is_subscription,
                    "expiration_days": package.expiration_days,
                },
            }

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get subscription details: {str(e)}",
            )
