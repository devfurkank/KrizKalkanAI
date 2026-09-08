"""M3 — Türkçe kriz metin motoru.

İki görev çok görevli olarak yürütülür (rapor 3.1 · M3):

    Görev A  — İddia çıkarımı
    Görev B1 — Manipülatif söylem sınıflandırması (8 etiket)
    Görev B2 — Niyet/koruma sınıflandırması (yardım_çağrısı, Kural 0'ı besler)

Model eğitilene kadar bu motor sözlük tabanlı çalışır; ürettiği sözleşme
(etiket → kalibre skor + kanıt) eğitilmiş modelinkiyle aynıdır, dolayısıyla
yerine model konduğunda çağıran katmanlar değişmez.
"""

from __future__ import annotations

import re

from krizkalkan_core.schemas import Evidence, ExtractedClaim, Signal, TextAnalysis
from krizkalkan_core.taxonomy import Certainty, ClaimType
from krizkalkan_core.taxonomy import ManipulationLabel as L
from krizkalkan_core.text import lexicon as lex
from krizkalkan_core.text import model as m3


def _span(text: str, needle: str) -> str | None:
    """Kanıt için karakter aralığı üretir."""
    idx = text.casefold().find(needle.casefold())
    if idx < 0:
        return None
    return f"{idx}–{idx + len(needle)}"


def _extract_claims(raw: str, norm: str) -> list[ExtractedClaim]:
    """Görev A — metinden yapılandırılmış iddia çıkarır."""
    location = next((lex.city_display(c) for c in lex.CITIES if re.search(rf"\b{c}", norm)), None)

    mag_match = lex.MAGNITUDE.search(norm)
    magnitude = mag_match.group(1).replace(".", ",") if mag_match else None

    time_expr = None
    for pattern, template in lex.TIME_EXPRESSIONS:
        m = re.search(pattern, norm)
        if m:
            time_expr = template.format(*m.groups()) if m.groups() else template
            break

    alleged_source = next(
        (name for pattern, name in lex.ALLEGED_SOURCES if re.search(pattern, norm)), None
    )

    if any(re.search(p, norm) for p in lex.CERTAINTY_ABSOLUTE):
        certainty = Certainty.MUTLAK
    elif any(re.search(p, norm) for p in lex.CERTAINTY_RUMOUR):
        certainty = Certainty.SOYLENTI
    else:
        certainty = Certainty.OLASILIKSAL

    # Desenler hizalı katlama üzerinde aranır; eşleşme konumu ham metne birebir
    # denk geldiği için iddia, özgün Türkçe yazımıyla gösterilebilir.
    aligned = lex.fold_aligned(raw)

    claims: list[ExtractedClaim] = []
    for claim_type, patterns in lex.CLAIM_PATTERNS.items():
        for pattern in patterns:
            m = re.search(pattern, aligned)
            if not m:
                continue
            claims.append(
                ExtractedClaim(
                    claim_type=ClaimType(claim_type),
                    text=raw[m.start() : m.end()].strip(),
                    location=location,
                    magnitude=magnitude,
                    time_expr=time_expr,
                    alleged_source=alleged_source,
                    certainty=certainty,
                )
            )
            break  # tür başına tek iddia yeterli

    if not claims and (location or magnitude or alleged_source):
        # Belirsiz iddiada tüm gönderi metni kullanılmaz; ilk cümle yeterlidir.
        # Aksi hâlde metnin herhangi bir yerindeki genel terim, alakasız bir
        # resmî kayıtla eşleşebilir.
        first_sentence = re.split(r"[.!?\n]", raw.strip())[0].strip()
        claims.append(
            ExtractedClaim(
                claim_type=ClaimType.BELIRSIZ,
                text=(first_sentence or raw.strip())[:110],
                location=location,
                magnitude=magnitude,
                time_expr=time_expr,
                alleged_source=alleged_source,
                certainty=certainty,
            )
        )
    return claims


def _help_call_score(norm: str) -> tuple[float, list[str]]:
    """Görev B2 — yardım çağrısı skoru.

    Negatif işaretler skoru düşürür ama sıfırlamaz: Kural 0 bilinçli olarak
    duyarlılık lehine asimetriktir (rapor 2.2 · Y3).
    """
    score, hits = lex.match_score(norm, lex.HELP_CALL_PATTERNS)
    if score <= 0:
        return 0.0, []
    penalty, _ = lex.match_score(norm, lex.HELP_CALL_NEGATIVES)
    return round(max(score - penalty * score, score * 0.55), 4), hits


def _sozluk_analizi(raw_text: str) -> tuple[TextAnalysis, list[Signal]]:
    """Sözlük tabanlı analiz — model yokken tek yol, varken yapı sağlayıcısı."""
    norm = lex.normalize(raw_text)

    # ── Görev B1 ──
    labels: dict[L, float] = {}
    label_hits: dict[L, list[str]] = {}
    for label, patterns in lex.PATTERNS.items():
        score, hits = lex.match_score(norm, patterns)
        if score > 0:
            labels[label] = score
            label_hits[label] = hits

    if labels:
        dominant = max(labels, key=lambda k: labels[k])
    else:
        dominant = L.NOTR_BILGILENDIRME
        labels[L.NOTR_BILGILENDIRME] = 1.0

    # ── Görev B2 ──
    help_score, help_hits = _help_call_score(norm)

    # ── Yalanlama çerçevesi ──
    debunk_score, debunk_hits = lex.match_score(norm, lex.DEBUNK_PATTERNS)

    # ── Görev A ──
    claims = _extract_claims(raw_text, norm)

    analysis = TextAnalysis(
        claims=claims,
        labels=labels,
        dominant_label=dominant,
        help_call_score=help_score,
        debunk_score=debunk_score,
    )

    # ── Sinyaller ──
    signals: list[Signal] = []

    manipulation = max((v for k, v in labels.items() if k is not L.NOTR_BILGILENDIRME), default=0.0)
    evidence = [
        Evidence(
            kind="metin_araligi",
            label=f"“{hit}” — {label.value}",
            locator=_span(raw_text, hit),
        )
        for label, hits in label_hits.items()
        if label is not L.NOTR_BILGILENDIRME
        for hit in hits[:2]
    ]
    signals.append(
        Signal(
            module="M3",
            key="text.manipulative",
            label="Manipülatif söylem",
            score=manipulation,
            raw_score=manipulation,
            abstained=len(norm) < 12,
            abstain_reason="Metin sınıflandırma için çok kısa" if len(norm) < 12 else None,
            evidence=evidence[:4],
        )
    )

    signals.append(
        Signal(
            module="M3",
            key="text.help_call",
            label="Yardım çağrısı",
            score=help_score,
            raw_score=help_score,
            evidence=[
                Evidence(
                    kind="metin_araligi",
                    label=f"“{hit}”",
                    locator=_span(raw_text, hit),
                    detail="Kural 0 koruma sinyali",
                )
                for hit in help_hits[:3]
            ],
        )
    )

    if debunk_score > 0:
        signals.append(
            Signal(
                module="M3",
                key="text.debunk",
                label="Yalanlama çerçevesi",
                score=debunk_score,
                raw_score=debunk_score,
                evidence=[
                    Evidence(
                        kind="metin_araligi",
                        label=f"“{hit}” — metin iddiayı öne sürmüyor, düzeltiyor",
                        locator=_span(raw_text, hit),
                    )
                    for hit in debunk_hits[:2]
                ],
            )
        )

    if claims:
        primary = claims[0]
        detail_parts = [
            p
            for p in (
                f"konum: {primary.location}" if primary.location else None,
                f"büyüklük: {primary.magnitude}" if primary.magnitude else None,
                f"zaman: {primary.time_expr}" if primary.time_expr else None,
                f"kaynak: {primary.alleged_source}" if primary.alleged_source else None,
                f"kesinlik: {primary.certainty.value}",
            )
            if p
        ]
        signals.append(
            Signal(
                module="M3",
                key="text.claim",
                label="İddia çıkarımı",
                score=1.0 if primary.certainty is Certainty.MUTLAK else 0.6,
                raw_score=1.0 if primary.certainty is Certainty.MUTLAK else 0.6,
                evidence=[
                    Evidence(
                        kind="metin_araligi",
                        label=f"{primary.claim_type.value}: “{primary.text}”",
                        locator=_span(raw_text, primary.text),
                        detail=" · ".join(detail_parts),
                    )
                ],
            )
        )

    return analysis, signals


# ─────────────────────────── Model yolu ───────────────────────────


def _model_kaniti(raw_text: str, kanitlar: list[tuple[str, int, int, float]]) -> list[Evidence]:
    """Örtme ölçümünü kanıt nesnelerine çevirir.

    Kanıt sözlük desenlerinden değil modelden gelir: her kelime metinden
    çıkarılıp skorun ne kadar düştüğü ölçülür. Açıklama böylece modelin
    kararını anlatır, sözlüğün kararını değil (rapor 2.2 · Y5).
    """
    return [
        Evidence(
            kind="metin_araligi",
            label=f"“{kelime}”",
            locator=f"{bas}–{son}",
            detail=f"Kural 0 koruma sinyali · kelime çıkarıldığında skor {dusus:.2f} düşüyor",
        )
        for kelime, bas, son, dusus in kanitlar
    ]


def _modelle_zenginlestir(
    raw_text: str, analysis: TextAnalysis, signals: list[Signal], model: m3.M3Model
) -> tuple[TextAnalysis, list[Signal]]:
    """Sözlük çıktısını model kararlarıyla değiştirir.

    İş bölümü bilinçlidir: model sınıflandırır, sözlük yapı çıkarır. Modelin
    iddia tipi başlığı var ama konum/büyüklük/zaman alanları yok; sekiz etiketli
    manipülatif söylem başlığı ise hiç eğitilmedi. Bu alanlar sözlükten gelmeye
    devam eder ve model kartında böyle beyan edilir.
    """
    cikti = model.analiz(raw_text)

    # ── Görev B2: Kural 0 — KARAR SÖZLÜKTE KALIR ──
    #
    # Modelin yardım çağrısı başlığı Kural 0'a BAĞLANMAZ. Gerekçe ölçülmüştür
    # (docs/metrikler/m3.md):
    #
    #   1. Başlığın 0,92 duyarlılığı yalnızca İngilizce üzerinde ölçüldü.
    #      Doğrulama kümesindeki 78 pozitifin tamamı HumAID'den gelir; Türkçe
    #      kaynaklarda bu etiket yoktur (bkz. docs/veri-envanteri.md · D3).
    #      Sayı çapraz dilli aktarımı ölçer, Türkçe başarımı değil.
    #
    #   2. Türkçe'de model, seferberlik söylemini yardım çağrısından
    #      ayıramıyor: "hepimiz sokağa dökülelim" metni SINANAN TÜM çalışma
    #      noktalarında (duyarlılık 0,80–0,95) korumaya alınıyor. Kural 0
    #      tetiklendiğinde sistem hiçbir müdahale uygulamadığı için bu,
    #      provokatif içeriğin etiketsiz geçmesi demek.
    #
    #   3. Aynı Türkçe metinlerde sözlük kusursuz ayırıyor: yardım çağrısı
    #      0,955 · provokatif/panik/tekzip/nötr 0,000.
    #
    # Model çıktısı yine de raporlanır — moderatöre ve kanıt paneline bilgi
    # olarak gider, karara girmez. Türkçe etiketli yardım çağrısı kümesi
    # oluşturulduğunda bu karar ölçümle yeniden ele alınmalıdır.
    model_skoru = model.yardim_skoru(cikti.yardim_olasilik)
    if model_skoru > analysis.help_call_score:
        signals.append(
            Signal(
                module="M3",
                key="text.help_call_model",
                label="Yardım çağrısı (model, bilgi amaçlı)",
                score=model_skoru,
                raw_score=model_skoru,
                evidence=_model_kaniti(raw_text, cikti.yardim_kanitlari)
                or [
                    Evidence(
                        kind="metin_araligi",
                        label="Model bu metni yardım çağrısına benzetiyor",
                        detail=(
                            "Bu sinyal Kural 0'a bağlı DEĞİLDİR: başlığın Türkçe "
                            "başarımı ölçülmemiştir."
                        ),
                    )
                ],
            )
        )

    # ── Görev A: iddia tipi ──
    # Yapılandırılmış alanlar (konum, büyüklük, zaman, kaynak) sözlükten korunur;
    # yalnızca tür modelin kararıyla değişir.
    if analysis.claims:
        analysis.claims[0] = analysis.claims[0].model_copy(update={"claim_type": cikti.claim_type})
    elif cikti.claim_type is not ClaimType.BELIRSIZ:
        analysis.claims = [
            ExtractedClaim(
                claim_type=cikti.claim_type,
                text=raw_text.strip()[:110],
                certainty=Certainty.OLASILIKSAL,
            )
        ]

    # ── Görev B1 yardımcısı: alan-genel yanlış bilgi ──
    # Karara katkı vermez; kanıt panelinde bağlam olarak gösterilir. Füzyona
    # bağlanması ayrı bir ölçüm gerektirir (docs/metrikler/m3.md).
    if cikti.yanlis_etiket == "yanlis":
        signals.append(
            Signal(
                module="M3",
                key="text.misinformation",
                label="Alan-genel yanlış bilgi işareti",
                score=cikti.yanlis_olasilik,
                raw_score=cikti.yanlis_olasilik,
                evidence=[
                    Evidence(
                        kind="metin_araligi",
                        label="Metin, yanlış bilgi kalıplarına benziyor",
                        detail=(
                            "Bu sinyal tek başına karar vermez; kanıt panelinde "
                            "bağlam olarak gösterilir."
                        ),
                    )
                ],
            )
        )

    return analysis, signals


def analyse(raw_text: str) -> tuple[TextAnalysis, list[Signal]]:
    """Metni analiz eder; TextAnalysis ve üretilen sinyalleri döndürür.

    Model yüklüyse sınıflandırma kararları ondan, yapısal çıkarım sözlükten
    gelir. Model yoksa sözlük tek başına çalışır ve sözleşme değişmez.
    """
    analysis, signals = _sozluk_analizi(raw_text)
    model = m3.get()
    if model is None:
        return analysis, signals
    return _modelle_zenginlestir(raw_text, analysis, signals, model)
