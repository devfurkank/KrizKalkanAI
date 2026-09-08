"""M1 — Köken ve yeniden-bağlam motoru.

Sistemin ilk sorusu budur: "bu içeriği daha önce gördük mü?" (rapor 1.2 ·
köken önceliği). Köken eşleşmesi gösterilebilir ve kesin bir kanıt ürettiği
için, olasılıksal sentetik medya analizinden önce çalıştırılır.
"""

from __future__ import annotations

import logging
from pathlib import Path

from krizkalkan_core.provenance import corpus, imaging, index
from krizkalkan_core.provenance.hashing import (
    MATCH_MAX_DISTANCE,
    hamming_distance,
    hex_of,
    perceptual_hash,
    similarity,
)
from krizkalkan_core.schemas import Evidence, ProvenanceMatch, Signal

logger = logging.getLogger(__name__)


def _medya_yolu(fingerprint: str) -> Path | None:
    """Parmak izi gerçek bir görüntü dosyasını mı işaret ediyor?

    Demo senaryoları medyayı bir dize parmak iziyle temsil eder; gerçek
    kullanımda ise dosya yolu gelir. İkisini ayırmak, demo davranışını
    bozmadan gerçek medya yolunu açar.
    """
    if not fingerprint or len(fingerprint) > 400 or "\n" in fingerprint:
        return None
    try:
        yol = Path(fingerprint)
    except (OSError, ValueError):
        return None
    return yol if yol.is_file() and imaging.gorsel_mi(yol) else None


def _indeks_eslesmesi(yol: Path) -> tuple[ProvenanceMatch, list[Evidence]] | None:
    """Gerçek görüntüyü köken indeksinde arar; indeks yoksa None."""
    indeks = index.get()
    if indeks is None:
        return None

    try:
        dhash, phash = imaging.karmalar(yol)
    except Exception:  # bozuk/okunamayan dosya köken sorgusunu düşürmemeli
        logger.warning("Görüntü okunamadı, köken sorgusu atlandı: %s", yol)
        return None

    adaylar = indeks.ara(dhash, phash, k=1)
    if not adaylar or not adaylar[0].eslesti:
        return ProvenanceMatch(matched=False), [
            Evidence(
                kind="ustveri",
                label="Referans indeksinde eşleşme bulunamadı",
                locator=f"dHash {dhash:016x}",
                detail=f"{len(indeks)} kayıt tarandı"
                + (f" · en yakın mesafe {adaylar[0].mesafe} bit" if adaylar else ""),
            )
        ]

    en_iyi = adaylar[0]
    kayit = en_iyi.kayit
    return (
        ProvenanceMatch(
            matched=True,
            similarity=en_iyi.benzerlik,
            first_published=kayit.ilk_yayin,
            source=kayit.lisans or "Wikimedia Commons",
            original_event=kayit.olay,
            original_location=kayit.konum,
            matched_frame=f"{en_iyi.karma_turu} · {en_iyi.mesafe} bit fark",
            corpus_id=kayit.kayit_id,
        ),
        [
            Evidence(
                kind="kare",
                label=f"Bu görüntü ilk kez {kayit.ilk_yayin or 'bilinmeyen tarihte'} yayımlanmış",
                locator=f"{en_iyi.karma_turu} · Hamming {en_iyi.mesafe}/64",
                detail=f"{kayit.kaynak_url or kayit.kayit_id} · lisans: {kayit.lisans or '—'}",
            ),
            Evidence(
                kind="kayit",
                label=f"Özgün olay: {kayit.olay}",
                detail=f"Özgün konum: {kayit.konum}",
            ),
        ],
    )


def lookup(fingerprint: str) -> tuple[ProvenanceMatch, corpus.CorpusEntry | None]:
    """Parmak izini referans korpusunda arar; en yakın kaydı döndürür."""
    query = perceptual_hash(fingerprint)

    best: corpus.CorpusEntry | None = None
    best_distance = MATCH_MAX_DISTANCE + 1
    for entry in corpus.ENTRIES:
        distance = hamming_distance(query, entry.phash)
        if distance < best_distance:
            best, best_distance = entry, distance

    if best is None or best_distance > MATCH_MAX_DISTANCE:
        return ProvenanceMatch(matched=False), None

    return (
        ProvenanceMatch(
            matched=True,
            similarity=similarity(query, best.phash),
            first_published=best.first_published,
            source=best.source,
            original_event=best.event,
            original_location=best.location,
            matched_frame=best.frame_label,
            corpus_id=best.corpus_id,
        ),
        best,
    )


def analyse(
    fingerprint: str | None, claimed_location: str | None = None
) -> tuple[ProvenanceMatch | None, list[Signal]]:
    """Medyanın kökenini analiz eder.

    `claimed_location` verilirse, eşleşen kaydın konumuyla karşılaştırılır ve
    uyuşmazlık ayrı bir kanıt olarak raporlanır.
    """
    if not fingerprint:
        return None, [
            Signal(
                module="M1",
                key="provenance.match",
                label="Köken eşleşmesi",
                score=0.0,
                raw_score=0.0,
                abstained=True,
                abstain_reason="İçerikte medya yok; köken sorgusu uygulanamaz",
            )
        ]

    # Gerçek görüntü geldiyse indeks üzerinden ara; demo parmak izleri
    # tohumlanmış korpusla eşleşmeye devam eder.
    if (yol := _medya_yolu(fingerprint)) is not None:
        sonuc = _indeks_eslesmesi(yol)
        if sonuc is not None:
            gercek_match, kanitlar = sonuc
            return gercek_match, [
                Signal(
                    module="M1",
                    key="provenance.match",
                    label=(
                        "Köken eşleşmesi (yeniden bağlam)"
                        if gercek_match.matched
                        else "Köken eşleşmesi"
                    ),
                    score=gercek_match.similarity,
                    raw_score=gercek_match.similarity,
                    evidence=kanitlar,
                )
            ]

    match, entry = lookup(fingerprint)

    if not match.matched or entry is None:
        return match, [
            Signal(
                module="M1",
                key="provenance.match",
                label="Köken eşleşmesi",
                score=0.0,
                raw_score=0.0,
                evidence=[
                    Evidence(
                        kind="ustveri",
                        label="Referans korpusunda eşleşme bulunamadı",
                        locator=hex_of(perceptual_hash(fingerprint)),
                        detail=f"{len(corpus.ENTRIES)} kayıt tarandı",
                    )
                ],
            )
        ]

    evidence = [
        Evidence(
            kind="kare",
            label=f"Bu görüntü ilk kez {match.first_published} tarihinde yayımlanmış",
            locator=match.matched_frame,
            detail=f"{match.source} · benzerlik {match.similarity:.2f} · {match.corpus_id}",
        ),
        Evidence(
            kind="kayit",
            label=f"Özgün olay: {match.original_event}",
            detail=f"Özgün konum: {match.original_location}",
        ),
    ]

    # Metindeki konum ile kaydın konumu çelişiyor mu?
    location_conflict = False
    if claimed_location and match.original_location:
        location_conflict = claimed_location.casefold() not in match.original_location.casefold()
        if location_conflict:
            evidence.append(
                Evidence(
                    kind="kayit",
                    label="Metindeki konum ile eşleşen kaydın konumu uyuşmuyor",
                    detail=f"metin: {claimed_location} · kayıt: {match.original_location}",
                )
            )

    score = match.similarity
    if location_conflict:
        score = min(1.0, score + 0.05)

    return match, [
        Signal(
            module="M1",
            key="provenance.match",
            label="Köken eşleşmesi (yeniden bağlam)",
            score=round(score, 4),
            raw_score=match.similarity,
            evidence=evidence,
        )
    ]
