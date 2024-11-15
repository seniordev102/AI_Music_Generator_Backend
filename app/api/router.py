from fastapi.routing import APIRouter

from app.api.admin.cost.route import router as cost_router
from app.api.admin.route import router as admin_router
from app.api.affiliate.route import router as affiliate_router
from app.api.auth.route import router as auth_router
from app.api.category.route import router as category_router
from app.api.chat.route import router as chat_router
from app.api.cms_playlist.route import router as cms_playlist_router

# from app.api.album.route import router as album_router
from app.api.collection.route import router as collection_router
from app.api.craft_my_song.route import router as craft_my_song_router
from app.api.credit_management.route import router as credit_management_router
from app.api.credit_packages.route import router as credit_packages_router
from app.api.email.route import router as email_router
from app.api.embed.route import router as embed_router
from app.api.favorite.route import router as favorite_router
from app.api.iah_radio.route import router as iah_radio_router
from app.api.oracle.route import router as oracle_router
from app.api.oracle.stt.route import router as stt_router
from app.api.perfom.route import router as perform_router
from app.api.playlist.route import router as playlist_router
from app.api.siv_playlist.route import router as sonic_iv_router
from app.api.sonic_playlist.route import router as sonic_playlist_router
from app.api.sonic_supplement.route import router as sonic_supplement_router
from app.api.sonic_supplement_category.route import (
    router as sonic_supplement_category_router,
)
from app.api.sra_chat.route import router as sra_chat_router
from app.api.stripe.route import router as stripe_router
from app.api.subscription.route import router as subscription_router
from app.api.subscription_config.route import router as subscription_config_router
from app.api.track.route import router as track_router
from app.api.user.route import router as user_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(user_router, prefix="/user", tags=["user"])
api_router.include_router(collection_router, prefix="/collection", tags=["collection"])

api_router.include_router(category_router, prefix="/category", tags=["category"])

api_router.include_router(
    sonic_supplement_category_router,
    prefix="/sonic-supplement-category",
    tags=["sonic-supplement-category"],
)

api_router.include_router(
    sonic_supplement_router, prefix="/sonic-supplement", tags=["sonic-supplement"]
)

api_router.include_router(track_router, prefix="/track", tags=["track"])
api_router.include_router(
    subscription_router, prefix="/subscription", tags=["subscription"]
)
api_router.include_router(
    subscription_config_router,
    prefix="/subscription-config",
    tags=["subscription configurations"],
)
api_router.include_router(oracle_router, prefix="/oracle", tags=["oracle"])
api_router.include_router(favorite_router, prefix="/favorite", tags=["favorite"])
api_router.include_router(playlist_router, prefix="/playlist", tags=["playlist"])
api_router.include_router(
    sonic_playlist_router, prefix="/sonic-playlist", tags=["sonic-playlist"]
)
api_router.include_router(
    cms_playlist_router,
    prefix="/craft-my-sonic-playlist",
    tags=["craft-my-sonic-playlist"],
)
api_router.include_router(
    sonic_iv_router,
    prefix="/sonic-iv-playlist",
    tags=["sonic-iv-playlist"],
)
api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_router.include_router(sra_chat_router, prefix="/sra-chat", tags=["sra-chat"])
api_router.include_router(email_router, prefix="/email", tags=["email"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_router.include_router(embed_router, prefix="/embed-player", tags=["embed-player"])
api_router.include_router(stt_router, prefix="/sst", tags=["speech-to-text"])
api_router.include_router(affiliate_router, prefix="/affiliate", tags=["affiliate"])
api_router.include_router(stripe_router, prefix="/stripe", tags=["iah-stripe"])
api_router.include_router(iah_radio_router, prefix="/iah-radio", tags=["iah-radio"])
api_router.include_router(
    craft_my_song_router, prefix="/craft-my-song", tags=["craft-my-song"]
)
api_router.include_router(perform_router, prefix="/perform", tags=["perform"])
api_router.include_router(
    credit_packages_router, prefix="/credit-package", tags=["credit-package"]
)
api_router.include_router(
    credit_management_router, prefix="/credit-management", tags=["credit-management"]
)
api_router.include_router(cost_router, prefix="/cost", tags=["cost"])
