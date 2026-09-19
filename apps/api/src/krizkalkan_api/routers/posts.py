"""Akış ve gönderi uç noktaları."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from krizkalkan_core.pipeline import pipeline
from krizkalkan_core.schemas import (
    AnalysisResult,
    AnalyzeRequest,
    CreatePostRequest,
    MediaRef,
    Post,
)

from krizkalkan_api.media import temporary_upload
from krizkalkan_api.seed import AUTHORS, MEDIA_BY_KIND
from krizkalkan_api.store import store

router = APIRouter(prefix="/api", tags=["gönderiler"])

#: Demoda oturum açan kullanıcı.
CURRENT_USER = AUTHORS["kullanici1"].model_copy(
    update={"name": "Furkan K.", "handle": "furkankeskin"}
)

#: Yüklenen medyanın gönderideki temsili. Dosya adı bilinçli olarak
#: saklanmaz: kişisel bilgi taşıyabilir ve analizde hiçbir rol oynamaz.
UPLOADED_MEDIA = {
    "image": MediaRef(kind="image", label="Yüklenen görsel", uploaded=True),
    "video": MediaRef(kind="video", label="Yüklenen video", uploaded=True),
}

Body = Annotated[str, Form(max_length=10_000)]
Audience = Annotated[Literal["herkes", "takipciler", "belirli"], Form()]


@router.get("/posts", response_model=list[Post])
def list_posts() -> list[Post]:
    """Akıştaki tüm gönderiler, yeniden eskiye."""
    return store.list_posts()


@router.get("/posts/{post_id}", response_model=Post)
def get_post(post_id: str) -> Post:
    post = store.get_post(post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Gönderi bulunamadı")
    return post


@router.post("/analyze", response_model=AnalysisResult)
def analyze(payload: AnalyzeRequest) -> AnalysisResult:
    """Paylaşmadan önce içeriği analiz eder (Akış 1).

    Gönderi oluşturmaz; kullanıcı analiz kartını görüp karar verir.
    """
    result = pipeline.analyse(
        body=payload.body,
        media_kind=payload.media_kind,
        media_fingerprint=payload.media_fingerprint,
        duration_seconds=payload.duration_seconds,
    )
    store.add_analysis(result)
    return result


@router.post("/analyze/media", response_model=AnalysisResult)
def analyze_media(file: Annotated[UploadFile, File()], body: Body = "") -> AnalysisResult:
    """Yüklenen gerçek görseli ya da videoyu paylaşmadan önce analiz eder (Akış 1).

    Medya modülleri (M1 köken indeksi, M2 sahne–iddia, M4 sentetik görüntü/video,
    C2PA) yalnızca gerçek dosyada çalışır. Dosya analiz biter bitmez silinir.
    """
    with temporary_upload(file) as (path, kind):
        result = pipeline.analyse(body=body, media_kind=kind, media_fingerprint=str(path))
    store.add_analysis(result)
    return result


@router.post("/posts", response_model=Post, status_code=201)
def create_post(payload: CreatePostRequest) -> Post:
    """Gönderiyi yayımlar.

    Paylaşım hiçbir koşulda engellenmez; sistem yalnızca analiz sonucunu
    gönderiye iliştirir (rapor 2.2 · Y3).
    """
    post_id = f"g_{uuid.uuid4().hex[:10]}"
    analysis = pipeline.analyse(
        body=payload.body,
        media_kind=payload.media_kind,
        media_fingerprint=payload.media_fingerprint,
        content_id=post_id,
    )
    return _publish(
        post_id=post_id,
        body=payload.body,
        audience=payload.audience,
        media=MEDIA_BY_KIND.get(payload.media_kind),
        analysis=analysis,
    )


@router.post("/posts/media", response_model=Post, status_code=201)
def create_post_with_media(
    file: Annotated[UploadFile, File()], body: Body = "", audience: Audience = "herkes"
) -> Post:
    """Gerçek görselli ya da videolu gönderiyi yayımlar; medya analiz sonrası saklanmaz."""
    post_id = f"g_{uuid.uuid4().hex[:10]}"
    with temporary_upload(file) as (path, kind):
        analysis = pipeline.analyse(
            body=body, media_kind=kind, media_fingerprint=str(path), content_id=post_id
        )
    return _publish(
        post_id=post_id,
        body=body,
        audience=audience,
        media=UPLOADED_MEDIA[kind],
        analysis=analysis,
    )


def _publish(
    *,
    post_id: str,
    body: str,
    audience: Literal["herkes", "takipciler", "belirli"],
    media: MediaRef | None,
    analysis: AnalysisResult,
) -> Post:
    """Analizi tamamlanmış gönderiyi akışa ekler ve denetim kaydına işler."""
    post = Post(
        id=post_id,
        author=CURRENT_USER,
        body=body,
        created_at=datetime.now(UTC),
        audience=audience,
        media=media,
        stats={"replies": 0, "quotes": 0, "boosts": 0, "views": 0},
        analysis=analysis,
        shared_despite_warning=analysis.intervention.level.value == "SEVIYE_3",
    )
    store.add_post(post)

    if analysis.intervention.protected_by_rule_zero:
        store.log(
            "koruma_kuralı_uygulandı",
            actor="sistem",
            post_id=post_id,
            detail="Kural 0 · yardım çağrısı korundu",
        )
    else:
        store.log(
            "gönderi_yayımlandı",
            actor="kullanıcı",
            post_id=post_id,
            detail=f"{analysis.verdict} · {analysis.intervention.label}",
        )
    return post
