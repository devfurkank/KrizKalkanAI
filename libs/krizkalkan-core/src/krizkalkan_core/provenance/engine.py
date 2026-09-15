"""M1 — Köken ve yeniden-bağlam motoru.

Sistemin ilk sorusu budur: "bu içeriği daha önce gördük mü?" (rapor 1.2 ·
köken önceliği). Köken eşleşmesi gösterilebilir ve kesin bir kanıt ürettiği
için, olasılıksal sentetik medya analizinden önce çalıştırılır.
"""

from __future__ import annotations

import logging
import re
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
from krizkalkan_core.text.lexicon import normalize

logger = logging.getLogger(__name__)

#: Sorgu dHash'inde bulunması gereken asgari bit sayısı.
#:
#: Tek renkli ya da neredeyse düz bir görüntünün dHash'i sıfıra yakındır ve
#: indeksteki düşük dokulu kayıtlara "yakın" düşer: düz kahverengi bir kare,
#: Halep müzesinin kırpılmış bir fotoğrafıyla 9 bit mesafede eşleşip yanlış
#: bağlam kararı üretiyordu. Ölçüm (1.758 kayıt): kayıtların %99,5'i ≥ 15 bit
#: taşır, en düşüğü 9 bittir; sıfır karmaya ≤ 10 bit uzaklıkta yalnızca 2 kayıt
#: vardır. Bu eşiğin altındaki sorgu bilgi taşımaz ve aranmaz.
ASGARI_KARMA_BITI = 12


def _konum_celiskisi(iddia_konumu: str | None, kayit_konumu: str | None) -> bool:
    """Metindeki konum ile kaydın konumu çelişiyor mu?

    Karşılaştırma `normalize()` üzerinden yapılır, casefold() ile değil:
    Python'da "İZMİR".casefold() birleşik noktalı i üretir ve "izmir" ile
    eşleşmez. Aynı tuzak M5'te derece etiketlerinde de yaşandı.

    Kayıt konumu "Adıyaman/Şanlıurfa" gibi birleşik olabilir; iddia edilen
    konum parçalardan biriyle örtüşüyorsa çelişki yoktur.
    """
    if not iddia_konumu or not kayit_konumu:
        return False
    iddia = normalize(iddia_konumu)
    parcalar = [normalize(p) for p in re.split(r"[/,]", kayit_konumu) if p.strip()]
    return not any(iddia in p or p in iddia for p in parcalar if p)


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


def _cekinme(neden: str, *kanitlar: Evidence) -> Signal:
    return Signal(
        module="M1",
        key="provenance.match",
        label="Köken eşleşmesi",
        score=0.0,
        raw_score=0.0,
        abstained=True,
        abstain_reason=neden,
        evidence=list(kanitlar),
    )


def _gercek_medya(
    yol: Path, claimed_location: str | None = None
) -> tuple[ProvenanceMatch | None, list[Signal]]:
    """Gerçek görüntünün kökenini referans indeksinde arar.

    Gerçek dosya hiçbir koşulda demo korpusuna DÜŞMEZ: o yol parmak izi
    dizesini karmalar, yani görüntü hakkında değil dosyanın adı hakkında
    konuşur. İndeks yoksa ya da görüntü aranamıyorsa modül çekinir.
    """
    indeks = index.get()
    if indeks is None:
        return None, [_cekinme("Köken referans indeksi yüklü değil")]

    try:
        dhash, phash = imaging.karmalar(yol)
    except Exception:  # bozuk/okunamayan dosya köken sorgusunu düşürmemeli
        logger.warning("Görüntü okunamadı, köken sorgusu atlandı: %s", yol)
        return None, [_cekinme("Görüntü okunamadı; köken sorgusu yapılamadı")]

    if (bit := dhash.bit_count()) < ASGARI_KARMA_BITI:
        return None, [
            _cekinme(
                "Görüntü ayırt edici ayrıntı taşımıyor; köken araması güvenilir olmaz",
                Evidence(
                    kind="ustveri",
                    label="Görüntü neredeyse düz: algısal karma bilgi taşımıyor",
                    locator=f"dHash {dhash:016x}",
                    detail=f"karmada {bit}/64 bit bilgi var · asgari {ASGARI_KARMA_BITI}",
                ),
            )
        ]

    match, kanitlar = _indeks_eslesmesi(indeks, dhash, phash, claimed_location)
    return match, [
        Signal(
            module="M1",
            key="provenance.match",
            label="Köken eşleşmesi (yeniden bağlam)" if match.matched else "Köken eşleşmesi",
            score=match.similarity,
            raw_score=match.similarity,
            evidence=kanitlar,
        )
    ]


def _indeks_eslesmesi(
    indeks: index.ProvenanceIndex, dhash: int, phash: int, claimed_location: str | None
) -> tuple[ProvenanceMatch, list[Evidence]]:
    """Karmaları indekste arar; eşleşme ve kanıtlarını döndürür."""
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
    celiski = _konum_celiskisi(claimed_location, kayit.konum)
    return (
        ProvenanceMatch(
            matched=True,
            similarity=en_iyi.benzerlik,
            context_conflict=celiski,
            conflict_detail=(
                f"metin: {claimed_location} · kayıt: {kayit.konum}" if celiski else None
            ),
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
            *(
                [
                    Evidence(
                        kind="kayit",
                        label="Metindeki konum ile eşleşen kaydın konumu uyuşmuyor",
                        detail=f"metin: {claimed_location} · kayıt: {kayit.konum}",
                    )
                ]
                if celiski
                else []
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
        return _gercek_medya(yol, claimed_location)

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
    location_conflict = _konum_celiskisi(claimed_location, match.original_location)
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

    match = match.model_copy(
        update={
            "context_conflict": location_conflict,
            "conflict_detail": (
                f"metin: {claimed_location} · kayıt: {match.original_location}"
                if location_conflict
                else None
            ),
        }
    )

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
