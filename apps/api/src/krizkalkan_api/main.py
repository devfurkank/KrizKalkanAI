"""FastAPI uygulama giriş noktası.

Analiz zinciri varsayılan olarak istek içinde (satır içi) çalışır; bu sayede
demo ortamı Redis/Celery olmadan tek komutla ayağa kalkar. `KK_INLINE_ANALYSIS`
kapatıldığında aynı boru hattı Celery işçisine devredilir (rapor 3.1 · kuyruk).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from krizkalkan_api import __version__
from krizkalkan_api.config import settings
from krizkalkan_api.routers import health, metrics, moderation, posts, radar
from krizkalkan_api.seed import seed
from krizkalkan_api.store import store


@asynccontextmanager
async def lifespan(_: FastAPI) -> Any:
    if settings.seed_on_startup:
        seed()
    yield


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description=(
        "Afet ve kriz dönemlerinde çok modlu bilgi bütünlüğü sistemi. "
        "Analiz modülleri: M1 köken · M2 çok modlu çelişki · M3 Türkçe kriz metni · "
        "M4 sentetik medya · M5 kriz bilgi havuzu · M6 kanıt füzyonu · M7 politika."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(posts.router)
app.include_router(moderation.router)
app.include_router(radar.router)
app.include_router(metrics.router)


@app.post("/api/demo/reset", tags=["demo"])
def reset_demo() -> dict[str, str | int]:
    """Demoyu başlangıç durumuna döndürür.

    Sunum sırasında akışı temizlemek için kullanılır; jüri önünde art arda
    senaryo gösterirken durumu sıfırlamayı sağlar.
    """
    seed()
    return {"durum": "tohum verisi yeniden yüklendi", "gönderi": len(store.posts)}
