import uuid as uuid_pkg
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


# create common models for the timestamp and uuid
class UUIDModel(SQLModel):
    id: uuid_pkg.UUID = Field(
        default_factory=uuid_pkg.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
        sa_column_kwargs={"server_default": text("gen_random_uuid()"), "unique": True},
    )


class TimestampModel(SQLModel):
    created_at: datetime = Field(
        default_factory=datetime.now,
        nullable=False,
        sa_column_kwargs={"server_default": text("current_timestamp(0)")},
    )

    updated_at: datetime = Field(
        default_factory=datetime.now,
        nullable=False,
        sa_column_kwargs={
            "server_default": text("current_timestamp(0)"),
            "onupdate": text("current_timestamp(0)"),
        },
    )


class PlaylistType(str, Enum):
    SONIC_SUPPLEMENT = "SS"
    CRAFT_MY_SONIC = "CMS"
    AKS_IAH_QUERY = "AIQ"
    SONIC_IV = "SIV"


class User(UUIDModel, TimestampModel, table=True):
    __tablename__ = "users"

    name: str = Field(nullable=False)
    email: str = Field(nullable=False, index=True, unique=True)
    hashed_password: str = Field(nullable=False)
    wallet_address: str = Field(nullable=True)
    profile_image: str = Field(nullable=True)
    provider: str = Field(nullable=True)
    provider_id: str = Field(nullable=True)
    role = Field(nullable=False, default="client", index=True)
    stripe_customer_id: str = Field(nullable=True, unique=True)
    subscription_plan: str = Field(nullable=False, default="free")
    subscription_id: str = Field(nullable=True)
    subscription_item_id: str = Field(nullable=True)
    stripe_price_id: str = Field(nullable=True)
    stripe_product_id: str = Field(nullable=True)
    subscription_status: str = Field(nullable=True)
    active_subscription_id: str = Field(nullable=True)
    subscription_cancel_id: str = Field(nullable=True)
    payment_interval: str = Field(nullable=True)
    subscription_cancel_at: int = Field(nullable=True)
    is_admin: bool = Field(default=False)
    is_active: bool = Field(default=False)
    monthly_limit_ask_iah_queries: int = Field(nullable=True, default=0)
    monthly_limit_craft_my_sonics: int = Field(nullable=True, default=0)
    monthly_limit_sonic_supplement_shuffles: int = Field(nullable=True, default=0)
    monthly_limit_super_sonic_shuffles: int = Field(nullable=True, default=0)
    monthly_limit_ask_iah_playlist_generation: int = Field(nullable=True, default=0)
    monthly_limit_ask_iah_image_generation: int = Field(nullable=True, default=0)
    numbers_of_ask_iah_queries: int = Field(nullable=True, default=0)
    numbers_of_craft_my_sonics: int = Field(nullable=True, default=0)
    numbers_of_sonic_supplement_shuffles: int = Field(nullable=True, default=0)
    numbers_of_super_sonic_shuffles: int = Field(nullable=True, default=0)
    numbers_of_ask_iah_playlist_generation: int = Field(nullable=True, default=0)
    numbers_of_ask_iah_image_generation: int = Field(nullable=True, default=0)
    invite_code: str = Field(nullable=True)
    email_rest_token: str = Field(nullable=True)
    email_rest_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    def dict(self, **kwargs):
        user_dict = super().model_dump(**kwargs)
        user_dict.pop("hashed_password", None)
        return user_dict


class Collection(UUIDModel, TimestampModel, table=True):
    __tablename__ = "collections"

    name: str = Field(nullable=False)
    user_id: uuid_pkg.UUID = Field(nullable=True)
    description: str = Field(nullable=True)
    short_description: str = Field(nullable=True)
    audience: str = Field(nullable=True)
    frequency: str = Field(nullable=True)
    genre: str = Field(nullable=True)
    tempo: str = Field(nullable=True)
    lead_producer: str = Field(nullable=True)
    chakra: str = Field(nullable=True)
    order_seq: int = Field(nullable=True, default=0)
    cover_image: str = Field(nullable=True)
    thumbnail_image: str = Field(nullable=True)
    square_cover_image: str = Field(nullable=True)
    square_thumbnail_image: str = Field(nullable=True)
    ipfs_cover_image: str = Field(nullable=True)
    ipfs_thumbnail_image: str = Field(nullable=True)
    is_active: bool = Field(default=True, nullable=True)
    is_hidden: bool = Field(default=False, nullable=True)
    is_private: bool = Field(default=False, nullable=True)
    is_index: bool = Field(default=False, nullable=True)
    is_delist: bool = Field(default=False, nullable=True)
    is_iah_radio: bool = Field(default=False, nullable=True)
    tool_tip: str = Field(nullable=True)
    crafted_by: uuid_pkg.UUID = Field(nullable=True)


class Track(UUIDModel, TimestampModel, table=True):
    __tablename__ = "tracks"

    collection_id: uuid_pkg.UUID = Field(nullable=False)
    user_id: uuid_pkg.UUID = Field(nullable=True)
    name: str = Field(nullable=False)
    description: str = Field(nullable=True)
    short_description: str = Field(nullable=True)
    tempo: str = Field(nullable=True)
    instrumental_audio_url: str = Field(nullable=True)
    upright_audio_url: str = Field(nullable=True)
    reverse_audio_url: str = Field(nullable=True)
    hires_audio_url: str = Field(nullable=True)
    upright_message: str = Field(nullable=True)
    reverse_message: str = Field(nullable=True)
    frequency: str = Field(nullable=True)
    frequency_meaning: str = Field(nullable=True)
    cover_image: str = Field(nullable=True)
    thumbnail_image: str = Field(nullable=True)
    ipfs_cover_image: str = Field(nullable=True)
    ipfs_thumbnail_image: str = Field(nullable=True)
    ipfs_instrumental_url: str = Field(nullable=True)
    ipfs_hires_url: str = Field(nullable=True)
    ipfs_upright_audio_url: str = Field(nullable=True)
    ipfs_reverse_audio_url: str = Field(nullable=True)
    order_seq: int = Field(nullable=True, default=0)
    track_technical_data: str = Field(nullable=True)
    track_metadata: str = Field(nullable=True)
    ai_metadata: str = Field(nullable=True)
    is_hidden: bool = Field(default=False, nullable=True)
    is_private: bool = Field(default=False, nullable=True)
    is_index: bool = Field(default=False, nullable=True)
    is_lyrical: bool = Field(default=False, nullable=True)
    srt_lyrics: str = Field(nullable=True)
    crafted_by: uuid_pkg.UUID = Field(nullable=True)
    status: str = Field(nullable=True, default="pending")
    error_message: str = Field(nullable=True)


class Assets(UUIDModel, TimestampModel, table=True):
    __tablename__ = "assets"

    collection_id: uuid_pkg.UUID = Field(nullable=False)
    user_id: uuid_pkg.UUID = Field(nullable=True)
    track_id: uuid_pkg.UUID = Field(nullable=True)
    wallet_address: str = Field(nullable=True)
    ipfs_hash: str = Field(nullable=True)
    json_metadata: str = Field(nullable=True)
    transaction_hash: str = Field(nullable=True)
    block_number: int = Field(nullable=True)
    token_id: int = Field(nullable=True)


class SonicSupplements(UUIDModel, TimestampModel, table=True):
    __tablename__ = "sonic_supplements"

    name: str = Field(nullable=False)
    description: str = Field(nullable=True)
    short_description: str = Field(nullable=True)
    benefits: str = Field(nullable=True)
    cover_image: str = Field(nullable=True)
    cover_thumbnail_image: str = Field(nullable=True)
    square_cover_image: str = Field(nullable=True)
    square_thumbnail_image: str = Field(nullable=True)
    track_ids: str = Field(nullable=True)
    order_seq: int = Field(nullable=True, default=0)


class Category(UUIDModel, TimestampModel, table=True):
    __tablename__ = "categories"

    name: str = Field(nullable=False)
    description: str = Field(nullable=True)
    cover_image: str = Field(nullable=True)
    square_image: str = Field(nullable=True)
    collection_ids: str = Field(nullable=True)
    order_seq: int = Field(nullable=True, default=0)
    is_active: bool = Field(default=True, nullable=True)


class SonicSupplementCategory(UUIDModel, TimestampModel, table=True):
    __tablename__ = "sonic_supplement_categories"

    name: str = Field(nullable=False)
    description: str = Field(nullable=True)
    cover_image: str = Field(nullable=True)
    square_image: str = Field(nullable=True)
    collection_ids: str = Field(nullable=True)
    order_seq: int = Field(nullable=True, default=0)
    is_active: bool = Field(default=True, nullable=True)


class SubscriptionConfiguration(UUIDModel, TimestampModel, table=True):
    __tablename__ = "subscription_configurations"

    subscription_name: str = Field(nullable=False)
    description: str = Field(nullable=True)
    cover_image: str = Field(nullable=True)
    monthly_price: float = Field(nullable=True)
    yearly_price: float = Field(nullable=True)
    stripe_monthly_product_id: str = Field(nullable=True)
    stripe_yearly_product_id: str = Field(nullable=True)
    stripe_monthly_price_id: str = Field(nullable=True)
    stripe_yearly_price_id: str = Field(nullable=True)
    is_active: bool = Field(default=True, nullable=True)
    numbers_of_ask_iah_queries: int = Field(nullable=True, default=0)
    numbers_of_craft_my_sonics: int = Field(nullable=True, default=0)
    numbers_of_sonic_supplement_shuffles: int = Field(nullable=True, default=0)
    numbers_of_super_sonic_shuffles: int = Field(nullable=True, default=0)
    numbers_of_ask_iah_playlist_generation: int = Field(nullable=True, default=0)
    numbers_of_ask_iah_image_generation: int = Field(nullable=True, default=0)


class FavoriteTrack(UUIDModel, TimestampModel, table=True):
    __tablename__ = "favorite_tracks"

    user_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    track_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    collection_id: uuid_pkg.UUID = Field(nullable=True, index=True)


class FavoriteIAHResponse(UUIDModel, TimestampModel, table=True):
    __tablename__ = "favorite_iah_responses"

    user_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    message_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    session_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    response: str = Field(nullable=True)


class ChatHistory(UUIDModel, TimestampModel, table=True):
    __tablename__ = "chat_history"

    user_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    message_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    session_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    message: str = Field(nullable=True)
    response: str = Field(nullable=True)
    track_ids: str = Field(nullable=True)
    image_url: str = Field(nullable=True)
    is_user: bool = Field(default=True, nullable=True)


class IAHChatSession(UUIDModel, TimestampModel, table=True):
    __tablename__ = "iah_chat_sessions"

    session_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    user_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    title: str = Field(nullable=False)
    is_pinned: bool = Field(default=False, nullable=True)
    pinned_at: datetime = Field(
        default_factory=datetime.now,
        nullable=True,
        sa_column_kwargs={"server_default": text("current_timestamp(0)")},
    )


class SRAChatHistory(UUIDModel, TimestampModel, table=True):
    __tablename__ = "sra_chat_history"

    user_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    message_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    session_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    message: str = Field(nullable=True)
    response: str = Field(nullable=True)
    track_ids: str = Field(nullable=True)
    image_url: str = Field(nullable=True)
    is_user: bool = Field(default=True, nullable=True)


class IAHSRAChatSession(UUIDModel, TimestampModel, table=True):
    __tablename__ = "iah_sra_chat_sessions"

    session_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    user_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    title: str = Field(nullable=False)
    is_pinned: bool = Field(default=False, nullable=True)
    pinned_at: datetime = Field(
        default_factory=datetime.now,
        nullable=True,
        sa_column_kwargs={"server_default": text("current_timestamp(0)")},
    )


class Playlist(UUIDModel, TimestampModel, table=True):
    __tablename__ = "playlists"

    user_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    name: str = Field(nullable=False)
    description: str = Field(nullable=True)
    short_description: str = Field(nullable=True)
    cover_image: str = Field(nullable=True)
    track_ids: str = Field(nullable=True)
    is_public: bool = Field(nullable=True, default=False)
    order_seq: int = Field(nullable=True, default=0)


class SonicPlaylist(UUIDModel, TimestampModel, table=True):
    __tablename__ = "sonic_playlists"

    user_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    name: str = Field(nullable=False)
    description: str = Field(nullable=True)
    cover_image: str = Field(nullable=True)
    cover_image_thumbnail: str = Field(nullable=True)
    square_image: str = Field(nullable=True)
    square_thumbnail_image: str = Field(nullable=True)
    cover_image_prompt: str = Field(nullable=True)
    square_image_prompt: str = Field(nullable=True)
    selected_track_ids: str = Field(nullable=True)
    selected_category: str = Field(nullable=True)
    selected_collection: str = Field(nullable=True)
    user_input_title: str = Field(nullable=True)
    user_input_prompt: str = Field(nullable=True)
    playlist_type: PlaylistType = Field(nullable=True)

    social_media_title: str = Field(nullable=True)
    social_media_description: str = Field(nullable=True)
    is_social_media: bool = Field(default=False, nullable=True)
    is_playlist: bool = Field(default=False, nullable=True)
    is_featured_in_home: bool = Field(default=False, nullable=True)
    is_pinned: bool = Field(default=False, nullable=True)
    order_seq: int = Field(nullable=True, default=0)


class AskIAHFileUpload(UUIDModel, TimestampModel, table=True):
    __tablename__ = "ask_iah_file_uploads"

    user_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    file_name: str = Field(nullable=False)
    file_url: str = Field(nullable=True)
    file_type: str = Field(nullable=False)
    file_size: int = Field(nullable=False)
    session_id: uuid_pkg.UUID = Field(nullable=False)
    file_content: str = Field(nullable=True)


class SRAFileUpload(UUIDModel, TimestampModel, table=True):
    __tablename__ = "sra_file_uploads"

    user_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    file_name: str = Field(nullable=False)
    file_url: str = Field(nullable=True)
    file_type: str = Field(nullable=False)
    file_size: int = Field(nullable=False)
    session_id: uuid_pkg.UUID = Field(nullable=False)
    file_content: str = Field(nullable=True)


class IAHUserPrompt(UUIDModel, TimestampModel, table=True):
    __tablename__ = "iah_user_prompts"

    user_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    user_prompt: str = Field(nullable=True)
    is_active: bool = Field(default=True)


class SRAUserPrompt(UUIDModel, TimestampModel, table=True):
    __tablename__ = "sra_user_prompts"

    user_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    user_prompt: str = Field(nullable=True)
    is_active: bool = Field(default=True)


class TrackEmbedding(UUIDModel, TimestampModel, table=True):
    __tablename__ = "track_embeddings"

    track_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    collection_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    embedding: List[float] = Field(sa_column=Column(Vector(1536), nullable=False))
    embedding_metadata: Optional[dict] = Field(
        sa_column=Column("metadata", JSON, nullable=True)
    )


class CollectionEmbedding(UUIDModel, TimestampModel, table=True):
    __tablename__ = "collection_embeddings"

    collection_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    embedding: List[float] = Field(sa_column=Column(Vector(1536), nullable=False))
    embedding_metadata: Optional[dict] = Field(
        sa_column=Column("metadata", JSON, nullable=True)
    )


class MusicRequestStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    FINISHED = "finished"
    ERROR = "error"
    READY = "ready"
    IN_PROGRESS = "in-progress"


class MusicVoiceType(str, Enum):
    FEMALE = "female"
    MALE = "male"


class IAHCraftMySong(UUIDModel, TimestampModel, table=True):
    __tablename__ = "iah_craft_my_songs"

    title: str = Field(nullable=False)
    request_id: str = Field(nullable=True)
    music_url: str = Field(nullable=True)
    streaming_url: str = Field(nullable=True)
    user_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    request_status: MusicRequestStatus = Field(
        nullable=True, default=MusicRequestStatus.PENDING
    )
    user_prompt: str = Field(nullable=False)
    song_style: str = Field(nullable=True)
    is_private: bool = Field(nullable=True, default=True)
    is_vocal: bool = Field(nullable=True, default=True)
    voice_type: MusicVoiceType = Field(nullable=True)
    genres: str = Field(nullable=True)
    music_cover_image_url: str = Field(nullable=True)
    music_cover_image_thumbnail_url: str = Field(nullable=True)
    shares_count: int = Field(nullable=True, default=0)
    plays_count: int = Field(nullable=True, default=0)
    likes_count: int = Field(nullable=True, default=0)
    cover_image_status: MusicRequestStatus = Field(
        nullable=True, default=MusicRequestStatus.PENDING
    )
    music_url_v2: str = Field(nullable=True)
    streaming_url_v2: str = Field(nullable=True)
    generated_timestamp: int = Field(nullable=True)
    upload_v1_url: str = Field(nullable=True)
    upload_v2_url: str = Field(nullable=True)
    song_duration_in_seconds: int = Field(nullable=True)


class ExcludeCategoriesType(str, Enum):
    IAH_RADIO = "iah_radio"
    SONIC_SUPPLEMENT = "sonic_supplement"
    CRAFT_MY_SONIC = "craft_my_sonic"
    ASK_IAH = "ask_iah"
    SEARCH = "search"
    MUSIC_CATALOG = "music_catalog"
    CRAFT_MY_SONG = "craft_my_song"


class SystemExcludeMusicCategory(UUIDModel, TimestampModel, table=True):
    __tablename__ = "system_exclude_music_categories"

    exclude_type: ExcludeCategoriesType = Field(nullable=False)
    category_ids: str = Field(nullable=True)


class TransactionType(str, Enum):
    CREDIT = "credit"  # Adding credits
    DEBIT = "debit"  # Using credits


class TransactionSource(str, Enum):
    STRIPE = "stripe"
    IN_APP_PURCHASE = "in_app_purchase"
    P2P_TRANSFER = "p2p_transfer"
    SUBSCRIPTION_RENEWAL = "subscription_renewal"
    API_USAGE = "api_usage"
    SYSTEM = "system"  # For system-level adjustments


class SubscriptionPlatform(str, Enum):
    STRIPE = "stripe"
    APPLE = "apple"
    GOOGLE = "google"


class SubscriptionPeriod(str, Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"


class CreditPackage(UUIDModel, TimestampModel, table=True):
    __tablename__ = "credit_packages"
    name: str
    credits: int
    price: float = Field(default=0.0)  # Default price in USD
    is_subscription: bool = Field(default=False)
    subscription_period: Optional[SubscriptionPeriod] = None

    expiration_days: Optional[int] = Field(default=None)  # New field for expiration

    # Platform-specific IDs
    stripe_product_id: Optional[str] = Field(default=None)
    stripe_price_id: Optional[str] = Field(default=None)
    apple_product_id: Optional[str] = Field(default=None)
    google_product_id: Optional[str] = Field(default=None)

    # Store platform-specific pricing details
    platform_metadata: Dict = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=True)
    )


class UserCreditBalance(UUIDModel, TimestampModel, table=True):
    __tablename__ = "user_credit_balances"

    user_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    package_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    transaction_id: uuid_pkg.UUID = Field(nullable=False, unique=True)
    initial_amount: int = Field(nullable=False)
    remaining_amount: int = Field(nullable=False)
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    consumed_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    is_active: bool = Field(default=True)


class CreditConsumptionLog(UUIDModel, TimestampModel, table=True):
    __tablename__ = "credit_consumption_logs"

    user_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    balance_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    transaction_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    amount: int = Field(nullable=False)
    api_endpoint: Optional[str] = Field(nullable=True)
    credit_consumption_metadata: Dict = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=True)
    )


class UserSubscription(UUIDModel, TimestampModel, table=True):
    __tablename__ = "user_subscriptions"
    user_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    package_id: uuid_pkg.UUID = Field(nullable=False)
    platform: SubscriptionPlatform = Field(nullable=False)
    platform_subscription_id: str = Field(nullable=False)
    status: str = Field(nullable=False)
    current_period_start: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    current_period_end: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    cancel_at_period_end: bool = Field(default=False)
    credits_per_period: int

    # For tracking subscription changes
    previous_package_id: Optional[uuid_pkg.UUID] = Field(nullable=True)
    upgrade_effective_date: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    # For yearly subscription with monthly allocation
    billing_cycle: str = Field(default="monthly")
    credit_allocation_cycle: str = Field(default="monthly")
    next_credit_allocation_date: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True, index=True)
    )
    last_credit_allocation_date: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )


class CreditAllocationHistory(UUIDModel, TimestampModel, table=True):
    __tablename__ = "credit_allocation_history"
    subscription_id: uuid_pkg.UUID = Field(
        nullable=False, foreign_key="user_subscriptions.id"
    )
    user_id: uuid_pkg.UUID = Field(nullable=False, foreign_key="users.id")
    transaction_id: uuid_pkg.UUID = Field(
        nullable=False, foreign_key="credit_transactions.id"
    )
    balance_id: uuid_pkg.UUID = Field(
        nullable=False, foreign_key="user_credit_balances.id"
    )
    allocation_id: str = Field(nullable=False, unique=True, index=True)
    credits_allocated: int = Field(nullable=False)
    allocation_period: str = Field(nullable=False)
    status: str = Field(nullable=False)


class FailedAllocation(UUIDModel, TimestampModel, table=True):
    __tablename__ = "failed_allocations"
    subscription_id: uuid_pkg.UUID = Field(
        nullable=False, foreign_key="user_subscriptions.id"
    )
    user_id: uuid_pkg.UUID = Field(nullable=False, foreign_key="users.id")
    allocation_id: str = Field(nullable=False, unique=True)
    retry_count: int = Field(default=0)
    next_retry_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True)
    )
    last_error: Optional[str] = Field(nullable=True)
    status: str = Field(default="pending", index=True)
    resolution_notes: Optional[str] = Field(nullable=True)


class AllocationDiscrepancy(UUIDModel, TimestampModel, table=True):
    __tablename__ = "allocation_discrepancies"
    subscription_id: uuid_pkg.UUID = Field(
        nullable=False, foreign_key="user_subscriptions.id"
    )
    user_id: uuid_pkg.UUID = Field(nullable=False, foreign_key="users.id")
    expected_allocation_date: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    last_allocation_date: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    status: str = Field(default="detected", index=True)
    resolution_notes: Optional[str] = Field(nullable=True)
    resolved_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )


class CreditTransaction(UUIDModel, TimestampModel, table=True):
    __tablename__ = "credit_transactions"
    user_id: uuid_pkg.UUID = Field(nullable=False, index=True)
    transaction_type: TransactionType = Field(nullable=False)
    transaction_source: TransactionSource = Field(nullable=False)
    amount: int = Field(nullable=False)
    balance_after: int = Field(nullable=False)
    description: str = Field(nullable=False)

    # Reference fields based on source
    api_endpoint: Optional[str] = Field(nullable=True)
    platform_transaction_id: Optional[str] = Field(nullable=True)
    related_transaction_id: Optional[uuid_pkg.UUID] = Field(nullable=True)
    subscription_id: Optional[uuid_pkg.UUID] = Field(nullable=True)
    package_id: Optional[uuid_pkg.UUID] = Field(nullable=True)

    # Additional metadata
    credit_metadata: Dict = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=True)
    )


class SonicIVCollections(UUIDModel, TimestampModel, table=True):
    __tablename__ = "sonic_iv_collections"
    collection_ids: str = Field(nullable=True)


class IAHCostPerAction(UUIDModel, TimestampModel, table=True):
    __tablename__ = "iah_cost_per_action"
    action_type: str = Field(nullable=False)
    cost: int = Field(nullable=False)
    endpoint: str = Field(nullable=False)
    is_active: bool = Field(default=True)


metadata = SQLModel.metadata
