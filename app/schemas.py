import uuid as uuid_pkg
from datetime import datetime
from enum import Enum
from typing import List, Optional, Union

from fastapi import File, Form, UploadFile
from pydantic import BaseModel, EmailStr

from app.models import (
    ExcludeCategoriesType,
    MusicVoiceType,
    PlaylistType,
    TransactionSource,
)


class CreateCollection(BaseModel):
    name: str
    user_id: Optional[uuid_pkg.UUID]
    description: Optional[str]
    short_description: Optional[str]
    audience: Optional[str]
    frequency: Optional[str]
    genre: Optional[str]
    lead_producer: Optional[str]
    chakra: Optional[str]
    order_seq: Optional[int]
    cover_image: Optional[str]
    square_cover_image: Optional[str]
    square_thumbnail_image: Optional[str]
    thumbnail_image: Optional[str]
    ipfs_cover_image: Optional[str]
    ipfs_thumbnail_image: Optional[str]
    is_hidden: Optional[bool]
    is_private: Optional[bool]
    is_delist: Optional[bool]
    is_iah_radio: Optional[bool]
    crafted_by: Optional[str]


class UpdateCollection(BaseModel):
    name: Optional[str]
    user_id: Optional[uuid_pkg.UUID]
    description: Optional[str]
    short_description: Optional[str]
    audience: Optional[str]
    frequency: Optional[str]
    genre: Optional[str]
    lead_producer: Optional[str]
    chakra: Optional[str]
    order_seq: Optional[int]
    cover_image: Optional[str]
    square_cover_image: Optional[str]
    square_thumbnail_image: Optional[str]
    thumbnail_image: Optional[str]
    ipfs_cover_image: Optional[str]
    ipfs_thumbnail_image: Optional[str]
    is_hidden: Optional[bool]
    is_private: Optional[bool]
    is_delist: Optional[bool]
    is_iah_radio: Optional[bool]
    crafted_by: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


class CreateTrack(BaseModel):
    name: str
    collection_id: uuid_pkg.UUID
    cover_image_file: UploadFile
    instrumental_audio_file: UploadFile
    upright_audio_file: Optional[UploadFile]
    reverse_audio_file: Optional[UploadFile]
    hires_audio_file: UploadFile
    user_id: Optional[uuid_pkg.UUID]
    upright_message: Optional[str]
    reverse_message: Optional[str]
    frequency: Optional[str]
    frequency_meaning: Optional[str]
    order_seq: Optional[int]
    track_metadata: Optional[str]
    crafted_by: Optional[str]

    async def parse_track_data(
        name: str = Form(...),
        collection_id: uuid_pkg.UUID = Form(...),
        cover_image_file: UploadFile = File(...),
        instrumental_audio_file: UploadFile = File(...),
        upright_audio_file: UploadFile = File(None),
        reverse_audio_file: UploadFile = File(None),
        hires_audio_file: UploadFile = File(...),
        user_id: Optional[uuid_pkg.UUID] = Form(None),
        upright_message: Optional[str] = Form(None),
        reverse_message: Optional[str] = Form(None),
        frequency: Optional[str] = Form(None),
        order_seq: Optional[int] = Form(None),
        track_metadata: Optional[str] = Form(None),
        frequency_meaning: Optional[str] = Form(None),
        crafted_by: Optional[str] = Form(None),
    ):
        return CreateTrack(
            name=name,
            collection_id=collection_id,
            cover_image_file=cover_image_file,
            instrumental_audio_file=instrumental_audio_file,
            upright_audio_file=upright_audio_file,
            reverse_audio_file=reverse_audio_file,
            hires_audio_file=hires_audio_file,
            user_id=user_id,
            upright_message=upright_message,
            reverse_message=reverse_message,
            frequency=frequency,
            frequency_meaning=frequency_meaning,
            track_metadata=track_metadata,
            order_seq=order_seq,
            crafted_by=crafted_by,
        )


class UpdateTrack(BaseModel):
    name: Optional[str]
    collection_id: Optional[uuid_pkg.UUID]
    user_id: Optional[uuid_pkg.UUID]
    upright_message: Optional[str]
    reverse_message: Optional[str]
    frequency: Optional[str]
    frequency_meaning: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    track_metadata: Optional[str]
    crafted_by: Optional[str]


class TrackCreate(BaseModel):
    collection_id: uuid_pkg.UUID
    user_id: Optional[uuid_pkg.UUID]
    name: str
    description: Optional[str]


class TrackUpdate(BaseModel):
    name: Optional[str]
    description: Optional[str]


class MintAsset(BaseModel):
    track_id: uuid_pkg.UUID
    wallet_address: str


class UpdateMintedAsset(BaseModel):
    token_id: int
    transaction_hash: str
    block_number: int


class CreateUser(BaseModel):
    name: str
    email: str
    password: str
    invite_code: Optional[str]


class RefreshToken(BaseModel):
    refresh_token: str


class LoginUser(BaseModel):
    email: str
    password: str


class SsoUserLoginRequest(BaseModel):
    email: str
    name: str
    image: Optional[str]
    provider: Optional[str]
    provider_id: Optional[str]
    invite_code: Optional[str]


class PasswordResetRequest(BaseModel):
    token: str
    email: str
    new_password: str


class PasswordResetRequestRequest(BaseModel):
    email: str
    origin: str


class UpdateUser(BaseModel):
    name: Optional[str]
    email: Optional[str]
    hashed_password: Optional[str]
    wallet_address: Optional[str]
    profile_image: Optional[str]
    provider: Optional[str]
    provider_id: Optional[str]
    role: Optional[str]
    is_admin: Optional[bool]
    is_active: Optional[bool]
    stripe_customer_id: Optional[str]
    subscription_plan: Optional[str]
    subscription_id: Optional[str]
    subscription_item_id: Optional[str]
    subscription_cancel_at: Optional[int]
    subscription_status: Optional[str]
    active_subscription_id: Optional[str]
    subscription_cancel_id: Optional[str]
    payment_interval: Optional[str]
    stripe_product_id: Optional[str]
    stripe_price_id: Optional[str]
    numbers_of_ask_iah_queries: Optional[int]
    numbers_of_craft_my_sonics: Optional[int]
    numbers_of_sonic_supplement_shuffles: Optional[int]
    numbers_of_super_sonic_shuffles: Optional[int]
    numbers_of_ask_iah_playlist_generation: Optional[int]
    numbers_of_ask_iah_image_generation: Optional[int]
    monthly_limit_ask_iah_queries: Optional[int]
    monthly_limit_craft_my_sonics: Optional[int]
    monthly_limit_sonic_supplement_shuffles: Optional[int]
    monthly_limit_super_sonic_shuffles: Optional[int]
    monthly_limit_ask_iah_playlist_generation: Optional[int]
    monthly_limit_ask_iah_image_generation: Optional[int]


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class CreateSonicSupplement(BaseModel):
    name: str
    description: Optional[str]
    short_description: Optional[str]
    benefits: Optional[str]
    cover_image: Optional[str]
    cover_thumbnail_image: Optional[str]
    square_cover_image: Optional[str]
    square_thumbnail_image: Optional[str]
    track_ids: Optional[str]
    order_seq: Optional[int]


class UpdateSonicSupplement(BaseModel):
    name: Optional[str]
    description: Optional[str]
    short_description: Optional[str]
    benefits: Optional[str]
    cover_image: Optional[str]
    cover_thumbnail_image: Optional[str]
    square_cover_image: Optional[str]
    square_thumbnail_image: Optional[str]
    track_ids: Optional[str]
    order_seq: Optional[int]
    created_at: Optional[str]
    updated_at: Optional[str]


class CreateCategory(BaseModel):
    name: str
    description: Optional[str]
    collection_ids: Optional[str]
    cover_image: Optional[str]
    square_image: Optional[str]
    order_seq: Optional[int]
    is_active: Optional[bool]


class UpdateCategory(BaseModel):
    name: Optional[str]
    description: Optional[str]
    collection_ids: Optional[str]
    cover_image: Optional[str]
    square_image: Optional[str]
    order_seq: Optional[int]
    is_active: Optional[bool]
    created_at: Optional[str]
    updated_at: Optional[str]


class CreateSonicSupplementCategory(BaseModel):
    name: str
    description: Optional[str]
    collection_ids: Optional[str]
    cover_image: Optional[str]
    square_image: Optional[str]
    order_seq: Optional[int]
    is_active: Optional[bool]


class UpdateSonicSupplementCategory(BaseModel):
    name: Optional[str]
    description: Optional[str]
    collection_ids: Optional[str]
    cover_image: Optional[str]
    square_image: Optional[str]
    order_seq: Optional[int]
    is_active: Optional[bool]
    created_at: Optional[str]
    updated_at: Optional[str]


class CreateSubscriptionConfig(BaseModel):
    subscription_name: str
    description: Optional[str]
    cover_image: Optional[str]
    monthly_price: Optional[float]
    yearly_price: Optional[float]
    stripe_monthly_product_id: Optional[str]
    stripe_yearly_product_id: Optional[str]
    is_active: Optional[bool]
    numbers_of_ask_iah_queries: Optional[int]
    numbers_of_craft_my_sonics: Optional[int]
    numbers_of_sonic_supplement_shuffles: Optional[int]
    numbers_of_super_sonic_shuffles: Optional[int]
    numbers_of_ask_iah_playlist_generation: Optional[int]
    numbers_of_ask_iah_image_generation: Optional[int]


class UpdateSubscriptionConfig(BaseModel):
    subscription_name: Optional[str]
    description: Optional[str]
    cover_image: Optional[str]
    monthly_price: Optional[float]
    yearly_price: Optional[float]
    stripe_monthly_product_id: Optional[str]
    stripe_yearly_product_id: Optional[str]
    stripe_monthly_price_id: Optional[str]
    stripe_yearly_price_id: Optional[str]
    is_active: Optional[bool]
    numbers_of_ask_iah_queries: Optional[int]
    numbers_of_craft_my_sonics: Optional[int]
    numbers_of_sonic_supplement_shuffles: Optional[int]
    numbers_of_super_sonic_shuffles: Optional[int]
    numbers_of_ask_iah_playlist_generation: Optional[int]
    numbers_of_ask_iah_image_generation: Optional[int]


class APIUsage(Enum):
    IAH_QUERY = "numbers_of_ask_iah_queries"
    CRAFT_MY_SONICS = "numbers_of_craft_my_sonics"
    SONIC_SUPPLEMENT_SHUFFLES = "numbers_of_sonic_supplement_shuffles"
    SUPER_SONIC_SHUFFLES = "numbers_of_super_sonic_shuffles"
    IAH_PLAYLIST_GENERATION = "numbers_of_ask_iah_playlist_generation"
    IAH_IMAGE_GENERATION = "numbers_of_ask_iah_image_generation"


class UpdateAPIUsage(BaseModel):
    update_key: APIUsage


class CreateFavoriteTrack(BaseModel):
    track_id: uuid_pkg.UUID
    collection_id: uuid_pkg.UUID


class CreateFavoritePromptResponse(BaseModel):
    message_id: uuid_pkg.UUID
    session_id: uuid_pkg.UUID
    response: Optional[str]


class CreatePlaylist(BaseModel):
    name: str
    description: Optional[str]
    short_description: Optional[str]
    cover_image: Optional[str]
    track_ids: Optional[List[str]]
    order_seq: Optional[int]
    is_public: Optional[bool]


class CopyPlaylist(BaseModel):
    name: Optional[str]
    description: Optional[str]
    cover_image: Optional[str]


class UpdatePlaylist(BaseModel):
    name: Optional[str]
    description: Optional[str]
    short_description: Optional[str]
    cover_image: Optional[str]
    track_ids: Optional[List[str]]
    order_seq: Optional[int]
    is_public: Optional[bool]


class UpdatePlaylistTracks(BaseModel):
    track_ids: Optional[List[str]]


class DeleteTrackFromPlaylist(BaseModel):
    track_id: uuid_pkg.UUID
    playlist_id: uuid_pkg.UUID


class AddTrackToPlaylist(BaseModel):
    track_id: uuid_pkg.UUID
    playlist_id: Union[uuid_pkg.UUID, None]


class CreateChatMessage(BaseModel):
    user_id: Optional[uuid_pkg.UUID]
    message_id: Optional[uuid_pkg.UUID]
    session_id: Optional[uuid_pkg.UUID]
    message: Optional[str]
    response: Optional[str]
    is_user: Optional[bool]
    image_url: Optional[str]
    track_ids: Optional[str]


class UpdateChatMetadata(BaseModel):
    message_id: Optional[uuid_pkg.UUID]
    session_id: Optional[uuid_pkg.UUID]
    image_url: Optional[str]
    track_ids: Optional[str]


class SendEmail(BaseModel):
    email: EmailStr
    name: str
    subject: str
    message: str


class SSGenerativeRequest(BaseModel):
    selected_category: uuid_pkg.UUID
    selected_collection: uuid_pkg.UUID
    selected_tracks: List[uuid_pkg.UUID]


class CreateSonicPlaylist(BaseModel):
    name: str
    description: Optional[str]
    selected_category: uuid_pkg.UUID
    selected_collection: uuid_pkg.UUID
    selected_track_ids: List[uuid_pkg.UUID]
    cover_image: Optional[str]
    cover_image_thumbnail: Optional[str]
    square_image: Optional[str]
    square_image_thumbnail: Optional[str]
    cover_image_prompt: Optional[str]
    square_image_prompt: Optional[str]
    playlist_type: Optional[PlaylistType]
    is_playlist: Optional[bool]
    is_featured_in_home: Optional[bool]


class UpdateSonicPlaylist(BaseModel):
    name: Optional[str]
    description: Optional[str]
    selected_category: Optional[uuid_pkg.UUID]
    selected_collection: Optional[uuid_pkg.UUID]
    selected_track_ids: Optional[List[uuid_pkg.UUID]]
    cover_image: Optional[str]
    cover_image_thumbnail: Optional[str]
    square_image: Optional[str]
    square_image_thumbnail: Optional[str]
    cover_image_prompt: Optional[str]
    square_image_prompt: Optional[str]
    playlist_type: Optional[PlaylistType]
    social_media_title: Optional[str]
    social_media_description: Optional[str]
    is_social_media: Optional[bool]
    is_playlist: Optional[bool]
    is_featured_in_home: Optional[bool]


class SelectedTrackList(BaseModel):
    selected_tracks: List[uuid_pkg.UUID]


class CraftMySonicTrackSummary(BaseModel):
    cms_playlist_title: Optional[str]
    cms_playlist_description: Optional[str]
    selected_tracks: List[uuid_pkg.UUID]


class GenerateCraftMySonicDetails(BaseModel):
    title: Optional[str]
    user_prompt: str
    selected_tracks: List[uuid_pkg.UUID]


class CreateCraftMySonicPlaylist(BaseModel):
    name: str
    description: Optional[str]
    cover_image: Optional[str]
    cover_image_thumbnail: Optional[str]
    square_image: Optional[str]
    square_image_thumbnail: Optional[str]
    selected_track_ids: List[uuid_pkg.UUID]
    user_input_title: Optional[str]
    user_input_prompt: Optional[str]
    playlist_type: Optional[PlaylistType]
    social_media_title: Optional[str]
    social_media_description: Optional[str]
    is_social_media: Optional[bool]
    is_playlist: Optional[bool]


class UpdateCraftMySonicPlaylist(BaseModel):
    name: Optional[str]
    description: Optional[str]
    cover_image: Optional[str]
    cover_image_thumbnail: Optional[str]
    square_image: Optional[str]
    square_image_thumbnail: Optional[str]
    selected_track_ids: Optional[List[uuid_pkg.UUID]]
    user_input_title: Optional[str]
    user_input_prompt: Optional[str]
    playlist_type: Optional[PlaylistType]
    social_media_title: Optional[str]
    social_media_description: Optional[str]
    is_social_media: Optional[bool]
    is_playlist: Optional[bool]


class GenerateCraftMySonicImage(BaseModel):
    user_prompt: str


class GetActiveCampaignContact(BaseModel):
    email: str


class GetTrackIds(BaseModel):
    track_ids: List[uuid_pkg.UUID]


class CreateIAHChatSession(BaseModel):
    user_id: uuid_pkg.UUID
    session_id: uuid_pkg.UUID
    title: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class CreateIAHSRAChatSession(BaseModel):
    user_id: uuid_pkg.UUID
    session_id: uuid_pkg.UUID
    title: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class ChangeChatSessionTitle(BaseModel):
    title: str


class CreateProfileImage(BaseModel):
    prompt: str


class ChangeChatSessionIsPinned(BaseModel):
    is_pinned: bool


class CreateOrUpdateUserPrompt(BaseModel):
    user_prompt: str
    is_active: bool


class CreateAffiliateUser(BaseModel):
    email: str


class GetStripeCoupon(BaseModel):
    coupon_name: str


class CreateStripeSubscription(BaseModel):
    customer_id: str
    price_id: str
    coupon_id: Optional[str]


class CreateIAHAffiliateUser(BaseModel):
    name: str
    email: EmailStr
    password: str


class CreateAffiliateStripeSubscription(BaseModel):
    customer_id: str
    payment_method_id: str
    price_id: str
    coupon_code: Optional[str] = None


class ValidateStripeUser(BaseModel):
    email: str


class AuthenticateAffiliateUser(BaseModel):
    email: str
    password: str


class UpdateStripeSubscription(BaseModel):
    subscription_id: str
    new_price_id: str
    coupon_id: Optional[str]


class ChangeSonicSupplementPinnedStatus(BaseModel):
    is_pinned: bool


class CreateCraftMySong(BaseModel):
    title: str
    is_private: bool
    is_vocal: bool
    voice_type: MusicVoiceType
    genres: str
    song_style: str
    user_prompt: str
    vibes: Optional[str]
    tempo: Optional[str]
    instruments: Optional[str]
    length: Optional[int]


class GenerateLyrics(BaseModel):
    user_prompt: str
    genres: Optional[str]
    song_style: Optional[str]
    vibe: Optional[str]
    tempo: Optional[str]
    instruments: Optional[str]
    length: Optional[int]


class GetIahRadioTracks(BaseModel):
    is_legacy: bool
    selected_collections: List[str]


class CreateExcludeCategory(BaseModel):
    exclude_type: ExcludeCategoriesType
    category_ids: List[str]


class CreditTransferRequest(BaseModel):
    to_email: str
    amount: int


class UpdatePackageRequest(BaseModel):
    name: Optional[str] = None
    credits: Optional[int] = None
    price: Optional[float] = None
    is_subscription: Optional[bool] = None
    subscription_period: Optional[str] = None
    platform_prices: Optional[dict] = None


class AddCreditsRequest(BaseModel):
    source: TransactionSource
    package_id: str
    platform_transaction_id: Optional[str] = None
    subscription_id: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[dict] = None


class DeductCreditsRequest(BaseModel):
    amount: int
    api_endpoint: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[dict] = None


class AdminAddCreditsRequest(BaseModel):
    user_email: EmailStr
    package_id: str
    description: str
    metadata: Optional[dict] = None


class CreatePaymentIntent(BaseModel):
    package_id: str
    coupon_name: Optional[str] = None
    payable_amount: float
    original_amount: float
    selected_payment_method_id: Optional[str] = None


class ValidateStripeCouponCode(BaseModel):
    coupon_name: str
    original_price: float


class AttachPaymentMethodToCustomer(BaseModel):
    payment_intent_id: str


class ValidateCreditTransferRequest(BaseModel):
    receiver_email: str
    amount: int


class GenerateSonicIVTracks(BaseModel):
    user_prompt: str


class GenerateSonicIVDetails(BaseModel):
    title: Optional[str]
    user_prompt: str
    selected_tracks: List[uuid_pkg.UUID]


class GenerateSonicIVImage(BaseModel):
    user_prompt: str


class CreateSonicIVPlaylistRequest(BaseModel):
    name: str
    description: Optional[str]
    cover_image: Optional[str]
    cover_image_thumbnail: Optional[str]
    square_image: Optional[str]
    square_image_thumbnail: Optional[str]
    selected_track_ids: List[uuid_pkg.UUID]
    user_input_title: Optional[str]
    user_input_prompt: Optional[str]
    playlist_type: Optional[PlaylistType]
    social_media_title: Optional[str]
    social_media_description: Optional[str]
    is_social_media: Optional[bool]
    is_playlist: Optional[bool]


class UpdateSonicIVPlaylistRequest(BaseModel):
    name: Optional[str]
    description: Optional[str]
    cover_image: Optional[str]
    cover_image_thumbnail: Optional[str]
    square_image: Optional[str]
    square_image_thumbnail: Optional[str]
    selected_track_ids: Optional[List[uuid_pkg.UUID]]
    user_input_title: Optional[str]
    user_input_prompt: Optional[str]
    playlist_type: Optional[PlaylistType]
    social_media_title: Optional[str]
    social_media_description: Optional[str]
    is_social_media: Optional[bool]
    is_playlist: Optional[bool]


class SonicIVPlaylistPinnedRequest(BaseModel):
    is_pinned: bool


class CraftMySongEditRequest(BaseModel):
    title: Optional[str]
    is_private: Optional[bool]


class CountType(str, Enum):
    PLAY = "play"
    SHARE = "share"
    LIKE = "like"


class CraftMySongUpdateCounts(BaseModel):
    count_type: CountType


class RegenerateCoverImageRequest(BaseModel):
    user_prompt: str


class CreateCostPerAction(BaseModel):
    action_type: str
    cost: int
    endpoint: str


class UpdateCostPerAction(BaseModel):
    action_type: str
    cost: int
