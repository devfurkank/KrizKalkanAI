# krizkalkan-worker

Celery tabanlı analiz kuyruğu işçisi. Yüklenen içerikler burada modül modül işlenir.

## Çalıştırma

```bash
celery -A krizkalkan_worker.app:celery_app worker --loglevel=info
```
