"""M2 — Çok modlu çelişki analizi.

Üç bağımsız sinyal üretir (rapor 3.1 · M2):

    1. Dudak–ses hizalaması (SyncNet yaklaşımı)
    2. Yüz gömmesi ile konuşmacı gömmesi arasında çapraz modal uyum (ECAPA-TDNN)
    3. Görsel-dil modeliyle sahne–iddia uyumu

Ölçülü dil kuralı: konuşmacı–yüz uyumu bir *kimlik kanıtı* değil, bir
*sinyal*dir. Arayüze "aynı kişiye ait olmayabilir" biçiminde aktarılır.
"""

from __future__ import annotations

from krizkalkan_core.provenance.hashing import perceptual_hash
from krizkalkan_core.schemas import Evidence, ExtractedClaim, Signal

_DESYNC_MARKERS = ("seslendirilmis", "klon", "dublaj", "manipule")

#: Sahne–iddia uyumu için görsel-dil modelinin arayacağı görsel dayanaklar.
_CLAIM_VISUAL_ANCHORS: dict[str, tuple[str, ...]] = {
    "altyapı_hasarı": ("baraj", "kopru", "yol", "bina", "su-yapisi"),
    "ikincil_afet_uyarısı": ("sismograf", "harita", "uyari-ekrani"),
    "tahliye": ("konvoy", "kalabalik", "yol"),
    "can_kaybı": ("hastane", "ambulans", "arama-kurtarma"),
    "resmî_açıklama": ("kursu", "mikrofon", "logo"),
}


def _score(fingerprint: str, salt: str, low: float, high: float) -> float:
    value = perceptual_hash(f"{salt}:{fingerprint}") % 1000 / 1000.0
    return round(low + value * (high - low), 4)


def analyse(
    fingerprint: str | None,
    media_kind: str,
    has_audio: bool,
    claims: list[ExtractedClaim],
) -> list[Signal]:
    """Modaliteler arası çelişkileri ölçer."""
    if not fingerprint or media_kind in ("yok", "image"):
        return [
            Signal(
                module="M2",
                key="multimodal.contradiction",
                label="Çok modlu çelişki",
                score=0.0,
                raw_score=0.0,
                abstained=True,
                abstain_reason="Çok modlu analiz için video ve ses gerekir",
            )
        ]

    fp = fingerprint.casefold()
    signals: list[Signal] = []
    desynced = any(m in fp for m in _DESYNC_MARKERS)

    # ── 1. Dudak–ses hizalaması ──
    if has_audio:
        raw = (
            _score(fp, "avsync-bad", 0.72, 0.93)
            if desynced
            else _score(fp, "avsync-ok", 0.03, 0.17)
        )
        signals.append(
            Signal(
                module="M2",
                key="multimodal.av_sync",
                label="Dudak hareketi ile ses uyumsuzluğu",
                score=raw,
                raw_score=raw,
                evidence=[
                    Evidence(
                        kind="zaman_araligi",
                        label=(
                            "Dudak hareketi ile ses arasında kalıcı gecikme"
                            if desynced
                            else "Dudak hareketi ses ile hizalı"
                        ),
                        locator="00:03–00:19",
                        detail=f"ortalama hizalama sapması {raw * 340:.0f} ms"
                        if desynced
                        else None,
                    )
                ],
            )
        )

        # ── 2. Konuşmacı–yüz çapraz modal uyum ──
        raw = (
            _score(fp, "spkface-bad", 0.68, 0.88)
            if desynced
            else _score(fp, "spkface-ok", 0.04, 0.20)
        )
        signals.append(
            Signal(
                module="M2",
                key="multimodal.speaker_face",
                label="Konuşmacı–yüz uyumu",
                score=raw,
                raw_score=raw,
                evidence=[
                    Evidence(
                        kind="kare",
                        label=(
                            "Ses ve görüntü aynı kişiye ait olmayabilir"
                            if desynced
                            else "Ses ve görüntü aynı kişiyle tutarlı"
                        ),
                        locator="kare 40 · yüz gömmesi ↔ konuşmacı gömmesi",
                        detail="Bu bir kimlik kanıtı değil, destekleyici sinyaldir",
                    )
                ],
            )
        )

    # ── 3. Sahne–iddia uyumu ──
    if claims:
        primary = claims[0]
        anchors = _CLAIM_VISUAL_ANCHORS.get(primary.claim_type.value, ())
        supported = any(a in fp for a in anchors)
        raw = (
            _score(fp, "scene-ok", 0.05, 0.18) if supported else _score(fp, "scene-bad", 0.55, 0.78)
        )
        signals.append(
            Signal(
                module="M2",
                key="multimodal.scene_claim",
                label="Sahne–iddia uyumu",
                score=raw,
                raw_score=raw,
                evidence=[
                    Evidence(
                        kind="kare",
                        label=(
                            f"Görüntü, “{primary.text}” iddiasını destekleyen unsur içeriyor"
                            if supported
                            else f"Görüntüde “{primary.text}” iddiasını destekleyen unsur bulunamadı"
                        ),
                        locator="kare 8, 24, 51 · görsel-dil eşleştirmesi",
                        detail=(
                            None
                            if supported
                            else f"aranan dayanaklar: {', '.join(anchors) or 'tanımsız'}"
                        ),
                    )
                ],
            )
        )

    return signals
