"""FastAPI uygulama giriş noktası."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from krizkalkan_api import __version__
from krizkalkan_api.config import settings
from krizkalkan_api.routers import health

app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="Afet ve kriz dönemlerinde çok modlu bilgi bütünlüğü sistemi",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
