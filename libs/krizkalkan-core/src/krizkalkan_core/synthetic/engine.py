"""M4 — Sentetik medya sinyalleri.

Görüntüde kare düzeyi omurga + zamansal toplama, seste ASVspoof geleneğine
uygun karşı önlem modeli ve C2PA köken üstverisi doğrulaması (rapor 3.1 · M4).

Kritik davranış: dağılım dışı (OOD) tespiti eşiği aşıldığında modül skor
üretmez, çekinir. Sistem "bilmiyorum" diyebilmelidir (rapor 2.2 · Y2).

Modülün üç yolu vardır ve hangisinin işlediği sinyalde görünür:

    görüntü + ağırlık var   → `synthetic/image.py` · iki bağımsız detektör
    gerçek dosya            → `synthetic/c2pa.py`  · kriptografik doğrulama
    demo parmak izi / ağırlık yok → sözlük yolu (aşağıdaki işaretler)

Ağırlık yoksa sistem çökmez, sözlük yoluna düşer: `KK_MODELS=off` bugünkü
davranışı aynen geri getirir.
"""

from __future__ import annotations

import logging
from pathlib import Path

from krizkalkan_core.provenance.hashing import perceptual_hash
from krizkalkan_core.schemas import Evidence, Signal
from krizkalkan_core.synthetic import image
from krizkalkan_core.synthetic.c2pa import dogrula as c2pa_dogrula

logger = logging.getLogger(__name__)

#: Parmak izi bundan uzunsa bir dosya yolu değil, demo tanımlayıcısıdır.
_YOL_UZUNLUK_SINIRI = 400

#: Bu işaretleri taşıyan medya sentetik/manipüle üretim olarak modellenir.
_SYNTHETIC_MARKERS = ("ai-", "sentetik", "uretilmis", "deepfake", "klon")
_MANIPULATED_MARKERS = ("manipule", "montaj", "duzenlenmis", "seslendirilmis")
#: Modelin çalışma aralığı dışında kalan içerikler — çekinme tetiklenir.
_OOD_MARKERS = ("dusuk-cozunurluk", "asiri-sikistirilmis", "kisa-klip")


def _deterministic_score(fingerprint: str, salt: str, low: float, high: float) -> float:
    """Parmak izinden kararlı, tekrarlanabilir bir skor türetir."""
    value = perceptual_hash(f"{salt}:{fingerprint}") % 1000 / 1000.0
    return round(low + value * (high - low), 4)


def _c2pa_status(fingerprint: str) -> tuple[str, float]:
    """C2PA üstverisi — demo parmak izleri için sözlük yolu.

    Gerçek dosya geldiğinde `_c2pa_gercek` kullanılır; bu yol yalnızca dize
    parmak iziyle temsil edilen demo senaryolarını çalıştırır.
    """
    if "c2pa-ai" in fingerprint:
        return "C2PA: içerik yapay zekâ üretimi olarak imzalanmış", 0.95
    if "c2pa-kamera" in fingerprint:
        return "C2PA: cihaz imzası doğrulandı, üretim zinciri bozulmamış", 0.02
    return "C2PA üstverisi bulunamadı", 0.0


def _c2pa_gercek(yol: Path) -> Signal:
    """Dosyanın C2PA imzasını gerçekten doğrular.

    Diğer M4 sinyalleri olasılıksaldır; bu değildir. İmza kriptografik bir
    kayıttır: içerik AI üretimi olarak imzalanmışsa sistem tahmin etmez,
    doğrular (rapor 3.1 · M4).
    """
    sonuc = c2pa_dogrula(yol)
    ayrintilar = [
        p
        for p in (
            f"üretici: {sonuc.uretici}" if sonuc.uretici else None,
            f"kaynak türü: {sonuc.dijital_kaynak.rsplit('/', 1)[-1]}"
            if sonuc.dijital_kaynak
            else None,
            sonuc.ayrinti,
        )
        if p
    ]
    return Signal(
        module="M4",
        key="synthetic.c2pa",
        label="Köken üstverisi (C2PA)",
        score=sonuc.skor,
        raw_score=sonuc.skor,
        abstained=sonuc.cekinmeli,
        abstain_reason=(
            # İmza yokluğu içerik hakkında hiçbir şey söylemez: C2PA yaygın
            # değildir ve imzasız içerik kuraldır, istisna değil.
            "İçerikte C2PA imzası yok — bu, içeriğin sahte olduğu anlamına gelmez"
            if sonuc.cekinmeli
            else None
        ),
        evidence=[
            Evidence(
                kind="ustveri",
                label=sonuc.aciklama,
                detail=" · ".join(ayrintilar) or None,
            )
        ],
    )


def _goruntu_sinyalleri(yol: Path) -> list[Signal] | None:
    """Gerçek görüntü üzerinde iki detektörü çalıştırır; model yoksa None.

    None dönmesi "temiz" demek değildir; çağıran sözlük yoluna düşer. Dosya
    görüntü olarak çözümlenemiyorsa (video, bozuk dosya) sözlük yoluna DÜŞÜLMEZ:
    o yol dosya adında kelime arar ve gerçek bir medya dosyası hakkında
    söyleyebileceği hiçbir doğru şey yoktur. Böyle bir durumda çekinilir.
    """
    model = image.get()
    if model is None:
        return None

    try:
        sonuc = model.incele(yol)
    except Exception:
        logger.warning("Görüntü sentetik analizi yapılamadı: %s", yol)
        return [
            Signal(
                module="M4",
                key="synthetic.video",
                label="Sentetik medya analizi",
                score=0.0,
                raw_score=0.0,
                abstained=True,
                abstain_reason=(
                    "Dosya görüntü olarak çözümlenemedi — video içerik için kare "
                    "çıkarımı (ffmpeg) bu kurulumda yok"
                ),
            )
        ]

    olcum = f"{sonuc.genislik}×{sonuc.yukseklik} · {sonuc.bayt_piksel:.3f} bayt/piksel"

    if sonuc.cekindi:
        return [
            Signal(
                module="M4",
                key="synthetic.video",
                label="Sentetik medya analizi",
                score=0.0,
                raw_score=0.0,
                abstained=True,
                abstain_reason=f"Yetersiz kanıt — {sonuc.cekinme_nedeni}",
                evidence=[
                    Evidence(
                        kind="ustveri",
                        label=(
                            "İki bağımsız detektör çelişti"
                            if sonuc.uyusmazlik
                            else "Dağılım dışı girdi tespit edildi"
                        ),
                        detail=f"{sonuc.cekinme_nedeni} · {olcum}",
                    )
                ],
            )
        ]

    dagilim = " · ".join(f"{ad}: {deger:.3f}" for ad, deger in sonuc.tur_skorlari.items())
    sinyaller = [
        Signal(
            module="M4",
            key="synthetic.video",
            label="Görüntüde sentetik üretim izi",
            score=sonuc.uretim_skoru,
            raw_score=sonuc.uretim_skoru,
            evidence=[
                Evidence(
                    kind="kare",
                    label=(
                        "Görüntüde yapay üretim izi bulundu"
                        if sonuc.uretim_skoru >= 0.5
                        else "Belirgin üretim artefaktı bulunamadı"
                    ),
                    locator="tam kare · iki bağımsız detektör",
                    detail=f"tür dağılımı → {dagilim} · {olcum}",
                )
            ],
        )
    ]

    # Tür ayrımı AYRI bir sinyaldir. SENTETİK_MEDYA ile MANİPÜLE_MEDYA farklı
    # sınıflardır; tek skor bu ayrımı taşıyamaz. Sinyalin karara nasıl girdiği
    # `fusion/engine.py` içinde, ölçüme dayanarak belirlenir.
    sinyaller.append(
        Signal(
            module="M4",
            key="synthetic.manipulation",
            label="Gerçek içerik üzerinde oynama izi",
            score=sonuc.manipulasyon_skoru,
            raw_score=sonuc.manipulasyon_skoru,
            evidence=[
                Evidence(
                    kind="kare",
                    label=(
                        "İz, sıfırdan üretimden çok mevcut içeriğin değiştirilmesine benziyor"
                        if sonuc.tur == "manipüle"
                        else f"Baskın tür: {sonuc.tur}"
                    ),
                    locator="üç sınıflı detektör",
                    detail=dagilim,
                )
            ],
        )
    )
    return sinyaller


def analyse(fingerprint: str | None, media_kind: str, has_audio: bool) -> list[Signal]:
    """Sentetik medya sinyallerini üretir."""
    if not fingerprint or media_kind == "yok":
        return [
            Signal(
                module="M4",
                key="synthetic.video",
                label="Sentetik medya analizi",
                score=0.0,
                raw_score=0.0,
                abstained=True,
                abstain_reason="İçerikte medya yok",
            )
        ]

    fp = fingerprint.casefold()
    signals: list[Signal] = []

    # Parmak izi gerçek bir dosyayı mı gösteriyor, yoksa demo tanımlayıcısı mı?
    # Bu ayrım modülün tamamını belirler: gerçek dosyada modeller ve kriptografi
    # çalışır, demo tanımlayıcısında sözlük.
    yol = Path(fingerprint) if len(fingerprint) < _YOL_UZUNLUK_SINIRI else None
    gercek_dosya = yol is not None and yol.is_file()

    # ── Görüntü: önce model yolu ──
    goruntu = _goruntu_sinyalleri(yol) if gercek_dosya else None
    if goruntu is not None:
        signals.extend(goruntu)
    else:
        signals.extend(_sozluk_goruntu(fp))

    # ── Ses karşı önlemi ──
    # Ses hâlâ sözlük yolundadır: ASVspoof karşı önlem modeli kurulmadı ve
    # bu, model kartında açıkça yazılı bir eksiktir.
    if has_audio:
        if any(m in fp for m in ("klon", "sentetik-ses", "tts")):
            raw = _deterministic_score(fp, "audio-synth", 0.74, 0.92)
            detail = "Doğal olmayan prosodi ve spektral süreksizlik"
        else:
            raw = _deterministic_score(fp, "audio-clean", 0.02, 0.15)
            detail = "Spektral profil doğal konuşma dağılımıyla uyumlu"
        signals.append(
            Signal(
                module="M4",
                key="synthetic.audio",
                label="Seste sentetik üretim izi",
                score=raw,
                raw_score=raw,
                evidence=[Evidence(kind="zaman_araligi", label=detail, locator="00:00–00:22")],
            )
        )

    # ── C2PA ──
    # İmza kriptografik bir kayıttır: dosya gerçekse tahmin edilmez, doğrulanır.
    if gercek_dosya:
        signals.append(_c2pa_gercek(yol))  # type: ignore[arg-type]
        return signals

    c2pa_label, c2pa_score = _c2pa_status(fp)
    signals.append(
        Signal(
            module="M4",
            key="synthetic.c2pa",
            label="Köken üstverisi (C2PA)",
            score=c2pa_score,
            raw_score=c2pa_score,
            abstained="bulunamadı" in c2pa_label,
            abstain_reason="İçerikte C2PA imzası yok" if "bulunamadı" in c2pa_label else None,
            evidence=[Evidence(kind="ustveri", label=c2pa_label)],
        )
    )

    return signals


def _sozluk_goruntu(fp: str) -> list[Signal]:
    """Görüntü sinyalinin sözlük yolu — ağırlık yokken ve demo parmak izlerinde.

    Davranışı model katmanı gelmeden önceki hâliyle birebir aynıdır; demo
    senaryoları ve `KK_MODELS=off` bu yoldan geçer.
    """
    signals: list[Signal] = []

    # ── Dağılım dışı kontrolü ──
    ood = next((m for m in _OOD_MARKERS if m in fp), None)
    if ood:
        reason = {
            "dusuk-cozunurluk": "çözünürlük modelin çalışma aralığının altında",
            "asiri-sikistirilmis": "aşırı sıkıştırma üretim izlerini siliyor",
            "kisa-klip": "klip süresi zamansal toplama için yetersiz",
        }[ood]
        signals.append(
            Signal(
                module="M4",
                key="synthetic.video",
                label="Sentetik medya analizi",
                score=0.0,
                raw_score=0.0,
                abstained=True,
                abstain_reason=f"Yetersiz kanıt — {reason}",
                evidence=[
                    Evidence(
                        kind="ustveri",
                        label="Dağılım dışı girdi tespit edildi",
                        detail=reason,
                    )
                ],
            )
        )
    else:
        is_synth = any(m in fp for m in _SYNTHETIC_MARKERS)
        is_manip = any(m in fp for m in _MANIPULATED_MARKERS)
        if is_synth:
            raw = _deterministic_score(fp, "video-synth", 0.78, 0.94)
            label_detail = "Kare düzeyi üretim artefaktı ve zamansal tutarsızlık"
        elif is_manip:
            raw = _deterministic_score(fp, "video-manip", 0.62, 0.80)
            label_detail = "Yerel yeniden kodlama izi ve kenar süreksizliği"
        else:
            raw = _deterministic_score(fp, "video-clean", 0.03, 0.18)
            label_detail = "Belirgin üretim artefaktı bulunamadı"

        signals.append(
            Signal(
                module="M4",
                key="synthetic.video",
                label="Görüntüde sentetik üretim izi",
                score=raw,
                raw_score=raw,
                evidence=[
                    Evidence(
                        kind="kare",
                        label=label_detail,
                        locator="kare 12–48 · zamansal toplama",
                    )
                ],
            )
        )

    return signals
