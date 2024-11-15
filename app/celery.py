from celery import Celery

from app.config import settings

celery_app = Celery(
    "worker",
    broker=settings.REDIS_BROKER_URL,
    backend=settings.REDIS_BACKEND_URL,
)
