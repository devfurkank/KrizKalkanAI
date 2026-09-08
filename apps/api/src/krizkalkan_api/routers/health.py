"""Sağlık kontrolü uç noktaları."""

from typing import Any

from fastapi import APIRouter
from krizkalkan_core.models import describe as describe_runtime
from krizkalkan_core.models import registry

from krizkalkan_api import __version__

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/health/modeller")
def model_health() -> dict[str, Any]:
    """Model katmanının durumu — sunum öncesi son kontrol noktası.

    Hiçbir modelin yüklü olmaması bir hata değildir: sistem o durumda kural
    tabanlı yolla eksiksiz çalışır. Uç nokta bunu gizlemez, açıkça raporlar.
    """
    report = registry.report()
    hazir = [ad for ad, bilgi in report.items() if bilgi["durum"] == "hazır"]
    return {
        "calisma_zamani": describe_runtime(),
        "modeller": report,
        "hazir_model_sayisi": len(hazir),
        "toplam_model_sayisi": len(report),
        "indirgenmis_mod": len(hazir) < len(report),
    }
