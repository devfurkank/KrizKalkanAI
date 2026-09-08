"""M5 iki aşamalı karar yolu — sahte modellerle davranış sözleşmesi.

Gerçek ağırlıklar Kaggle'da eğitiliyor; bu testler karar mantığının onlar
geldiğinde doğru çalışacağını garanti eder. Sahte modeller, gerçeklerinin
sözleşmesini birebir taklit eder.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from krizkalkan_core.knowledge import corpus, engine
from krizkalkan_core.knowledge.nli import Cikarim
from krizkalkan_core.taxonomy import KnowledgeVerdict


@dataclass
class SahteAday:
    record_id: str
    benzerlik: float


class SahteArayici:
    """Verilen kayıtları benzerlik sırasına göre döndürür."""

    def __init__(self, kimlikler: list[str], benzerlik: float = 0.85) -> None:
        self._adaylar = [SahteAday(k, benzerlik) for k in kimlikler]

    def ara(self, iddia: str, k: int = 5) -> list[SahteAday]:
        return self._adaylar[:k]


class SahteCikarimci:
    """Sırayla verilen çıkarımları döndürür."""

    def __init__(self, cikarimlar: list[Cikarim]) -> None:
        self._cikarimlar = cikarimlar

    def siniflandir(self, ciftler: list[tuple[str, str]]) -> list[Cikarim]:
        return self._cikarimlar[: len(ciftler)]


@pytest.fixture
def yanlis_kayit_kimligi() -> str:
    """Derecesi 'yanlış' olan bir tohum kaydın kimliği."""
    for k in corpus.records():
        if engine._verdict_of(k) is KnowledgeVerdict.CELISIYOR:
            return k.record_id
    pytest.skip("havuzda ÇELİŞİYOR dereceli kayıt yok")


def test_ayni_iddia_celisiyor_verir(yanlis_kayit_kimligi: str) -> None:
    """Çıkarım 'aynı iddia' derse kaydın derecesi karara dönüşür."""
    eslesme = engine._iki_asamali_yol(
        "baraj yıkıldı şehri terk edin",
        SahteArayici([yanlis_kayit_kimligi]),
        SahteCikarimci([Cikarim(etiket="entailment", olasilik=0.93)]),
    )
    assert eslesme.record is not None
    assert eslesme.verdict is KnowledgeVerdict.CELISIYOR
    assert eslesme.yol == "iki_asamali"
    assert eslesme.guven == 0.93


def test_dusuk_guvenli_entailment_karar_vermez(yanlis_kayit_kimligi: str) -> None:
    """Eşiğin altındaki çıkarım eşleşme sayılmaz.

    Yanlış eşleşme, kullanıcıya "resmî kaynak seni yalanlıyor" demek anlamına
    gelir; eşik bu yüzden kasten yüksektir.
    """
    eslesme = engine._iki_asamali_yol(
        "baraj yıkıldı",
        SahteArayici([yanlis_kayit_kimligi]),
        SahteCikarimci([Cikarim(etiket="entailment", olasilik=0.55)]),
    )
    assert eslesme.record is None
    assert eslesme.verdict is KnowledgeVerdict.KAYNAK_SESSIZ


def test_benzer_konu_ayni_iddia_degildir(yanlis_kayit_kimligi: str) -> None:
    """Yüksek benzerlik + 'neutral' çıkarım → eşleşme YOK.

    Ölçümün gösterdiği asıl hata modu budur: resmî duyurular havuza konu
    olarak çok benzer skor alıyor ama aynı iddiayı öne sürmüyor.
    """
    eslesme = engine._iki_asamali_yol(
        "afad koordinasyonunda ekipler sahada çalışmaya devam ediyor",
        SahteArayici([yanlis_kayit_kimligi], benzerlik=0.89),
        SahteCikarimci([Cikarim(etiket="neutral", olasilik=0.97)]),
    )
    assert eslesme.record is None, "benzerlik yüksek diye eşleşme kurulmamalı"
    assert eslesme.verdict is KnowledgeVerdict.KAYNAK_SESSIZ


def test_tekzip_paylasan_kullanici_desteklenir(yanlis_kayit_kimligi: str) -> None:
    """Yalanlanan iddianın TERSİNİ söyleyen metin dezenformasyon değildir."""
    eslesme = engine._iki_asamali_yol(
        "baraj yıkılmadı, DSİ yapısal hasar olmadığını açıkladı",
        SahteArayici([yanlis_kayit_kimligi]),
        SahteCikarimci([Cikarim(etiket="contradiction", olasilik=0.91)]),
    )
    assert eslesme.verdict is KnowledgeVerdict.DESTEKLIYOR


def test_ilk_uygun_aday_secilir(yanlis_kayit_kimligi: str) -> None:
    """İlk aday uymazsa sonraki adaylara bakılır (Recall@5'in anlamı budur)."""
    kimlikler = [k.record_id for k in corpus.records()][:3]
    kimlikler[2] = yanlis_kayit_kimligi
    eslesme = engine._iki_asamali_yol(
        "test",
        SahteArayici(kimlikler),
        SahteCikarimci(
            [
                Cikarim(etiket="neutral", olasilik=0.90),
                Cikarim(etiket="neutral", olasilik=0.88),
                Cikarim(etiket="entailment", olasilik=0.82),
            ]
        ),
    )
    assert eslesme.record is not None
    assert eslesme.record.record_id == yanlis_kayit_kimligi


def test_aday_yoksa_kaynak_sessiz() -> None:
    eslesme = engine._iki_asamali_yol("test", SahteArayici([]), SahteCikarimci([]))
    assert eslesme.record is None
    assert eslesme.verdict is KnowledgeVerdict.KAYNAK_SESSIZ


def test_modeller_yoksa_sozluk_yoluna_dusulur(monkeypatch) -> None:
    """Ağırlık yokken sistem bugünkü kural tabanlı davranışını sürdürür.

    Koşul ortama bırakılmaz, açıkça kurulur: aksi hâlde test yalnızca ağırlık
    dizini boş olduğu için geçer ve modeller eğitildiğinde sessizce anlamını
    yitirirdi.
    """
    monkeypatch.setattr(engine.retriever, "get", lambda: None)
    monkeypatch.setattr(engine.nli, "get", lambda: None)

    eslesme = engine._eslestir("AFAD ikinci büyük deprem uyarısı yaptı")
    assert eslesme.yol == "sozluk"
    assert eslesme.verdict is KnowledgeVerdict.CELISIYOR, "demo senaryosu korunmalı"


def test_tek_model_yeterli_degil(monkeypatch, yanlis_kayit_kimligi: str) -> None:
    """İki aşamalı yol her iki model de yüklüyken devreye girer.

    Yalnızca geri getirici varken karar benzerliğe kalırdı; ölçüm bunun
    güvenli olmadığını gösterdi (docs/metrikler/m5.md).
    """
    monkeypatch.setattr(engine.retriever, "get", lambda: SahteArayici([yanlis_kayit_kimligi]))
    monkeypatch.setattr(engine.nli, "get", lambda: None)
    assert engine._eslestir("baraj yıkıldı").yol == "sozluk"
