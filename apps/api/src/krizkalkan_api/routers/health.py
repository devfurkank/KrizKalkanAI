"""Sağlık kontrolü uç noktaları."""

from fastapi import APIRouter

from krizkalkan_api import __version__

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
