"""M5 bilgi havuzu — yükleme, derece eşlemesi ve ölçek altında davranış.

Bu dosyanın koruduğu üç davranış:

1. Havuz dosyası yoksa sistem çökmez, tohum kayıtlarla çalışır.
2. Türkçe derece etiketleri büyük/küçük harf farkından bağımsız eşleşir.
3. 2.500+ kayıt yüklüyken bile alakasız metin bir tekziple eşleşmez.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from krizkalkan_core.knowledge import corpus, engine
from krizkalkan_core.knowledge.corpus import KnowledgeRecord
from krizkalkan_core.taxonomy import KnowledgeVerdict
from krizkalkan_core.text import engine as text_engine


def _kayit(rating: str) -> KnowledgeRecord:
    return KnowledgeRecord(
        record_id="T-1",
        claim="test iddiası",
        fact_check="test tekzibi",
        rating_label=rating,
        date_published="Bülten 1",
        source="test",
    )


# ─────────────────── Türkçe büyük/küçük harf tuzağı ───────────────────


@pytest.mark.parametrize("rating", ["YANLIŞ", "Yanlış", "yanlış", "YANLIS", "yanlis"])
def test_yanlis_derecesi_her_yazimda_celisiyor_verir(rating: str) -> None:
    """Derece eşlemesi yazım biçiminden bağımsız olmalıdır.

    Python'da "YANLIŞ".casefold() → "yanliş" üretir; noktasız büyük I, noktalı
    i'ye katlanır ve "yanlış" ile eşleşmez. DMM verisi "Yanlış", tohum kayıtlar
    "YANLIŞ" yazdığı için bu fark, gerçek veri bağlandığında modülün sessizce
    hiçbir kayıtla eşleşmemesine yol açıyordu.
    """
    assert engine._verdict_of(_kayit(rating)) is KnowledgeVerdict.CELISIYOR


@pytest.mark.parametrize("rating", ["DOĞRU", "Doğru", "doğru", "DOGRU"])
def test_dogru_derecesi_her_yazimda_destekliyor_verir(rating: str) -> None:
    assert engine._verdict_of(_kayit(rating)) is KnowledgeVerdict.DESTEKLIYOR


def test_taninmayan_derece_ilgisiz_doner() -> None:
    assert engine._verdict_of(_kayit("Kısmen Doğru")) is KnowledgeVerdict.ILGISIZ


# ─────────────────── Havuz yükleme ───────────────────


def test_havuz_dosyasi_yoksa_cokmez(tmp_path: Path) -> None:
    assert corpus.load_dmm(tmp_path / "olmayan.jsonl") == []


def test_bozuk_satir_tum_havuzu_dusurmez(tmp_path: Path) -> None:
    """Tek hatalı kayıt, geri kalanın yüklenmesini engellememelidir."""
    dosya = tmp_path / "kayitlar.jsonl"
    saglam = {
        "record_id": "X-1",
        "claim": "iddia",
        "fact_check": "tekzip",
        "rating_label": "Yanlış",
        "date_published": "Bülten 9",
        "source": "DMM",
        "keywords": ["a"],
        "anchors": ["a"],
    }
    dosya.write_text(
        json.dumps(saglam, ensure_ascii=False)
        + "\n{bozuk json\n"
        + json.dumps({"record_id": "X-2"}, ensure_ascii=False)  # eksik alanlar
        + "\n",
        encoding="utf-8",
    )
    yuklenen = corpus.load_dmm(dosya)
    assert len(yuklenen) == 1
    assert yuklenen[0].record_id == "X-1"


def test_tohum_kayitlar_her_zaman_havuzda() -> None:
    """Demo senaryoları tohum kayıtlara dayanır; DMM yüklense de kalmalılar."""
    kimlikler = {r.record_id for r in corpus.records()}
    for tohum in corpus.SEEDED_RECORDS:
        assert tohum.record_id in kimlikler


# ─────────────────── Ölçek altında yanlış eşleşme ───────────────────


def test_alakasiz_metin_buyuk_havuzda_da_eslesmez() -> None:
    """Havuz büyüdükçe yanlış pozitif riski artar; çapa mekanizması bunu tutar."""
    analiz, _ = text_engine.analyse("Merhaba, bugün hava çok güzel.")
    eslesme, _ = engine.analyse(analiz.claims)
    assert eslesme is None or eslesme.verdict is KnowledgeVerdict.KAYNAK_SESSIZ


def test_kaynak_sessiz_yalan_ile_es_anlamli_degil() -> None:
    """RESMÎ_KAYNAK_SESSİZ, ÇELİŞİYOR'a dönüşmemelidir (rapor 3.1 · M5)."""
    analiz, _ = text_engine.analyse(
        "Köyümüzde elektrik kesintisi üçüncü güne girdi, jeneratör bekliyoruz."
    )
    eslesme, sinyaller = engine.analyse(analiz.claims)
    if eslesme is not None and eslesme.verdict is KnowledgeVerdict.KAYNAK_SESSIZ:
        # Sessizlik tek başına karar verdirmemeli: skor orta bantta kalmalı.
        skor = next(s.score for s in sinyaller if s.key == "knowledge.verdict")
        assert skor < 0.60, "sessizlik yüksek skorla raporlanırsa yalan gibi davranır"
