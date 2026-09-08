"""M6 — Kalibre kanıt füzyonu.

Üç aşamalıdır (rapor 3.1 · M6):

    1. Her modülün ham skoru isotonic regresyonla gerçek olasılığa çevrilir,
    2. Kalibre sinyaller kasten yorumlanabilir tutulmuş bir sınıflandırıcıya verilir,
    3. Katkı veren her sinyal kanıtıyla birlikte kanıt grafında saklanır.

Sınıflandırıcı monoton kısıtlıdır: her kural, bir sinyalin artmasının ilgili
sınıfın olasılığını yalnızca artırabileceği biçimde yazılmıştır. Bu, kararın
tek tek sinyallere kadar izlenebilmesini sağlar.
"""

from __future__ import annotations

from krizkalkan_core.fusion.calibration import calibrate
from krizkalkan_core.schemas import KnowledgeMatch, ProvenanceMatch, Signal, TextAnalysis
from krizkalkan_core.taxonomy import (
    ABSTENTION_FLOOR,
    ABSTENTION_THRESHOLD,
    VERDICT_MEANING,
    KnowledgeVerdict,
    Verdict,
)


def apply_calibration(signals: list[Signal]) -> list[Signal]:
    """Her sinyalin skorunu kalibre eder; ham skoru saklar."""
    for signal in signals:
        if signal.abstained:
            signal.score = 0.0
            continue
        signal.score = calibrate(signal.key, signal.raw_score)
    return signals


def _active(signals: list[Signal], key: str) -> float:
    """Çekinmemiş bir sinyalin kalibre skoru; yoksa 0."""
    for s in signals:
        if s.key == key:
            return 0.0 if s.abstained else s.score
    return 0.0


def _confidence_label(value: float) -> str:
    if value >= 0.75:
        return "yüksek"
    if value >= 0.50:
        return "orta"
    return "düşük"


def fuse(
    signals: list[Signal],
    provenance: ProvenanceMatch | None,
    text: TextAnalysis | None,
    knowledge: KnowledgeMatch | None,
) -> tuple[Verdict, float, list[Signal]]:
    """Sinyalleri birleştirip sınıf ve güven üretir.

    Karar sırası köken önceliğine göredir: kesin kanıt üreten sinyaller,
    olasılıksal olanlardan önce değerlendirilir (rapor 1.2).

    Dönen üçüncü değer, karara *katkı veren* sinyallerin listesidir; kanıt
    paneli bu listeden çizilir.
    """
    prov = _active(signals, "provenance.match")
    synth_video = _active(signals, "synthetic.video")
    synth_audio = _active(signals, "synthetic.audio")
    c2pa = _active(signals, "synthetic.c2pa")
    av_sync = _active(signals, "multimodal.av_sync")
    speaker_face = _active(signals, "multimodal.speaker_face")
    scene_claim = _active(signals, "multimodal.scene_claim")
    manipulative = _active(signals, "text.manipulative")
    know = _active(signals, "knowledge.verdict")

    by_key = {s.key: s for s in signals}

    def contributors(*keys: str) -> list[Signal]:
        return [by_key[k] for k in keys if k in by_key and not by_key[k].abstained]

    # ── 1. Köken önceliği: yanlış bağlam kesin kanıttır ──
    #
    # Eşleşmenin TEK BAŞINA yanlış bağlam anlamına gelmediğine dikkat: görüntü
    # gerçekten o olaya aitse ve metin de onu söylüyorsa bağlam doğrudur ve
    # eşleşme içeriği DESTEKLEYEN bir kanıttır. Sınıf ancak kaydın konumu/olayı
    # metindeki iddiayla çeliştiğinde kurulur.
    if provenance and provenance.matched and prov >= 0.60 and provenance.context_conflict:
        return (
            Verdict.YANLIS_BAGLAM,
            min(0.97, prov),
            contributors("provenance.match", "text.manipulative", "knowledge.verdict"),
        )

    # ── 2. Sentetik medya ──
    synthetic_evidence = max(synth_video, synth_audio, c2pa)
    if synthetic_evidence >= 0.62:
        return (
            Verdict.SENTETIK_MEDYA,
            min(0.96, synthetic_evidence),
            contributors(
                "synthetic.video", "synthetic.audio", "synthetic.c2pa", "multimodal.av_sync"
            ),
        )

    # ── 3. Manipüle medya: gerçek kayıt üzerinde oynama ──
    manipulation_evidence = max(av_sync, speaker_face)
    if manipulation_evidence >= 0.58:
        # İki bağımsız çok modlu sinyal aynı yönü gösteriyorsa güven artar.
        agreement = 0.06 if min(av_sync, speaker_face) >= 0.45 else 0.0
        return (
            Verdict.MANIPULE_MEDYA,
            min(0.95, manipulation_evidence + agreement),
            contributors("multimodal.av_sync", "multimodal.speaker_face", "synthetic.audio"),
        )

    # ── 4. Doğrulanmamış iddia ──
    # Yalanlama çerçevesi: metin iddiayı öne sürmüyor, düzeltiyorsa
    # doğrulanmamış iddia olarak sınıflanamaz. Tekziplerin dezenformasyon
    # sanılması bilinen bir hata modudur; burada yapısal olarak engellenir.
    debunking = bool(text and text.debunk_score >= 0.55)
    has_claim = bool(text and text.claims) and not debunking
    if (
        not debunking
        and knowledge
        and knowledge.verdict is KnowledgeVerdict.CELISIYOR
        and know >= 0.60
    ):
        return (
            Verdict.DOGRULANMAMIS_IDDIA,
            min(0.94, know),
            contributors("knowledge.verdict", "text.claim", "text.manipulative"),
        )
    if (
        has_claim
        and knowledge
        and knowledge.verdict is KnowledgeVerdict.KAYNAK_SESSIZ
        and (manipulative >= 0.35 or scene_claim >= 0.50)
    ):
        # Sessizlik tek başına yeterli değildir; manipülatif dil veya sahne
        # çelişkisi eşlik etmelidir.
        confidence = 0.45 + 0.30 * max(manipulative, scene_claim)
        return (
            Verdict.DOGRULANMAMIS_IDDIA,
            min(0.88, round(confidence, 4)),
            contributors(
                "knowledge.verdict",
                "text.claim",
                "text.manipulative",
                "multimodal.scene_claim",
            ),
        )

    # ── 5. Provokatif çerçeveleme ──
    if manipulative >= 0.55:
        return (
            Verdict.PROVOKATIF_CERCEVELEME,
            min(0.92, manipulative),
            contributors("text.manipulative", "text.claim"),
        )

    # ── 6. Çekinme ──
    # Yalanlama metinlerinde bilgi havuzu sinyali içeriği DESTEKLER (iddianın
    # yanlış olduğunu teyit eder), dolayısıyla aleyhte kanıt sayılmaz.
    strongest = max(prov, synthetic_evidence, manipulation_evidence, manipulative, scene_claim)
    if not debunking:
        strongest = max(strongest, know)
    informative = [s for s in signals if not s.abstained]

    if not informative:
        return Verdict.YETERSIZ_KANIT, 0.0, signals

    # Medya analiz edildi ama sentetik medya modülü karar veremediyse, sentetik
    # olma olasılığı dışlanamaz. Diğer modüller de bir şey bulmadıysa dürüst
    # cevap "bilmiyorum"dur — "temiz" değil.
    synth_signal = by_key.get("synthetic.video")
    if synth_signal is not None and synth_signal.abstained and strongest < ABSTENTION_FLOOR:
        return (
            Verdict.YETERSIZ_KANIT,
            round(1.0 - strongest, 4),
            [*informative, synth_signal],
        )

    # Belirsizlik bandı: zayıf ama sıfır olmayan sinyal, az sayıda modül.
    if ABSTENTION_FLOOR <= strongest < ABSTENTION_THRESHOLD and len(informative) < 3:
        return Verdict.YETERSIZ_KANIT, round(1.0 - strongest, 4), informative

    # ── 7. Temiz ──
    return Verdict.TEMIZ, round(1.0 - strongest, 4), informative


def describe(verdict: Verdict) -> str:
    return VERDICT_MEANING[verdict]


def confidence_label(value: float) -> str:
    return _confidence_label(value)
