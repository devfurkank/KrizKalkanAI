"""Celery uygulama örneği."""

from celery import Celery

from krizkalkan_worker.config import settings

celery_app = Celery(
    "krizkalkan",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["krizkalkan_worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Istanbul",
    enable_utc=True,
    task_track_started=True,
)
