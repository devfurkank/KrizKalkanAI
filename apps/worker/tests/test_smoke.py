"""İskelet doğrulama testi."""

from krizkalkan_worker.app import celery_app


def test_celery_uygulamasi_olusuyor() -> None:
    assert celery_app.main == "krizkalkan"
