"""Analiz görevleri.

Şu an yalnızca iskelet doğrulama görevi içerir; modül görevleri
(M1-M7) geliştirildikçe buraya eklenecektir.
"""

from krizkalkan_worker.app import celery_app


@celery_app.task(name="krizkalkan.ping")
def ping() -> str:
    """Kuyruğun ayakta olduğunu doğrular."""
    return "pong"
