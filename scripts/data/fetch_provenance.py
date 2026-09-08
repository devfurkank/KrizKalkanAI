#!/usr/bin/env python
"""M1 köken referans korpusunu toplar — Wikimedia Commons.

Korpus, "bu görüntüyü daha önce gördük mü?" sorusunun cevabını taşır. Her kayıt
bir **olay** ve **konum** etiketi taşır; yanlış bağlam tespiti bu iki alanın
metindeki iddiayla çelişmesine dayanır (rapor 3.1 · M1).

Commons seçildi çünkü üç şeyi birlikte veriyor: açık lisans, yayın tarihi ve
il düzeyinde olay kategorisi. Bu bir etiketleme işi değil indeksleme işidir.

Küçük boy (640 piksel) indirilir: algısal karma 8×8 ızgaraya indirgediği için
daha yüksek çözünürlük karmayı değiştirmez, yalnızca indirme süresini ve diski
büyütür.

Çıktı: data/external/provenance/{goruntuler/, kayitlar.jsonl}
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
HEDEF = REPO_ROOT / "data" / "external" / "provenance"
GORUNTU_DIZINI = HEDEF / "goruntuler"
KAYIT_DOSYASI = HEDEF / "kayitlar.jsonl"

API = "https://commons.wikimedia.org/w/api.php"
KULLANICI_AJANI = "KrizKalkanAI/0.1 (TEKNOFEST 2026 arastirma; github.com/devfurkank)"
KUCUK_BOY = 640

#: İstekler arası bekleme ve ilk geri çekilme süresi (saniye).
#: Commons hız sınırı agresif; nazik davranmak yeniden denemeden ucuz.
ISTEK_ARASI = 1.0
ILK_BEKLEME = 5.0


@dataclass(frozen=True, slots=True)
class Kategori:
    """Bir Commons kategorisi ve temsil ettiği olay/konum."""

    ad: str
    olay: str
    konum: str


#: Türkiye odaklı afet kategorileri. İl düzeyinde hasar kategorileri bilinçli
#: olarak ayrı tutulur: konum alanı, yanlış bağlam tespitinin dayanağıdır.
KATEGORILER: tuple[Kategori, ...] = (
    Kategori(
        "Category:Damage of the 2023 Kahramanmaraş earthquakes in Hatay",
        "6 Şubat 2023 Kahramanmaraş depremleri",
        "Hatay",
    ),
    Kategori(
        "Category:Damage of the 2023 Kahramanmaraş earthquakes in Gaziantep",
        "6 Şubat 2023 Kahramanmaraş depremleri",
        "Gaziantep",
    ),
    Kategori(
        "Category:Damage of the 2023 Kahramanmaraş earthquakes in Adıyaman",
        "6 Şubat 2023 Kahramanmaraş depremleri",
        "Adıyaman",
    ),
    Kategori(
        "Category:Damage of the 2023 Kahramanmaraş earthquakes in Osmaniye",
        "6 Şubat 2023 Kahramanmaraş depremleri",
        "Osmaniye",
    ),
    Kategori(
        "Category:Damage of the 2023 Kahramanmaraş earthquakes in Diyarbakır",
        "6 Şubat 2023 Kahramanmaraş depremleri",
        "Diyarbakır",
    ),
    Kategori(
        "Category:Damage of the 2023 Kahramanmaraş earthquakes",
        "6 Şubat 2023 Kahramanmaraş depremleri",
        "Kahramanmaraş",
    ),
    Kategori(
        "Category:Search and rescue operations during the 2023 Kahramanmaraş earthquakes",
        "6 Şubat 2023 Kahramanmaraş depremleri",
        "Deprem bölgesi",
    ),
    Kategori("Category:2023 Hatay earthquake", "20 Şubat 2023 Hatay depremi", "Hatay"),
    Kategori("Category:2021 Turkish wildfires", "2021 Akdeniz orman yangınları", "Antalya/Muğla"),
    Kategori("Category:2021 Milas fire", "2021 Milas yangını", "Muğla / Milas"),
    Kategori(
        "Category:2023 Adıyaman-Şanlıurfa flood disaster",
        "2023 Adıyaman-Şanlıurfa sel felaketi",
        "Adıyaman/Şanlıurfa",
    ),
    Kategori("Category:2022 Ankara floods", "2022 Ankara selleri", "Ankara"),
    Kategori("Category:Floods in Turkey", "Türkiye'de seller (arşiv)", "Türkiye"),
    Kategori("Category:Earthquakes in Turkey", "Türkiye'de depremler (arşiv)", "Türkiye"),
    Kategori("Category:2020 Aegean Sea earthquake", "2020 İzmir depremi", "İzmir"),
)


def _oturum() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = KULLANICI_AJANI
    return s


def _sorgu(oturum: requests.Session, parametreler: dict, deneme: int = 5) -> dict:
    """API sorgusu — hız sınırında üstel geri çekilerek yeniden dener.

    Commons yoğunlukta HTTP 429 ve düz metin gövde döndürüyor. Ham `.json()`
    çağrısı bunu JSONDecodeError olarak gösterip gerçek sebebi gizliyordu;
    ayrıca requests'in JSONDecodeError'ı bu sürümde ValueError'dan türemediği
    için genel `except ValueError` de yakalamıyor. Durum kodu bu yüzden
    gövdeden ÖNCE kontrol edilir.
    """
    bekleme = ILK_BEKLEME
    for _ in range(deneme):
        yanit = oturum.get(API, params={**parametreler, "maxlag": "5"}, timeout=60)
        if yanit.status_code == 200:
            try:
                veri = yanit.json()
            except Exception:  # düz metin/HTML hata gövdesi
                veri = None
            if veri is not None and "error" not in veri:
                return veri
        print(f"\n    ⏳ API {yanit.status_code}, {bekleme:.0f} sn…", end="", flush=True)
        time.sleep(bekleme)
        bekleme *= 2
    raise RuntimeError(f"API yanıt vermedi (son durum {yanit.status_code})")


def _uyeler(oturum: requests.Session, kategori: str, tip: str, limit: int) -> list[dict]:
    """Kategorinin dosya veya alt kategori üyelerini sayfalayarak toplar."""
    uyeler: list[dict] = []
    devam: dict[str, str] = {}
    while len(uyeler) < limit:
        parametreler = {
            "action": "query",
            "format": "json",
            "generator": "categorymembers",
            "gcmtitle": kategori,
            "gcmtype": tip,
            "gcmlimit": "100",
            **devam,
        }
        if tip == "file":
            parametreler |= {
                "prop": "imageinfo",
                "iiprop": "url|timestamp|extmetadata|size|mime",
                "iiurlwidth": str(KUCUK_BOY),
            }
        veri = _sorgu(oturum, parametreler)
        uyeler.extend(veri.get("query", {}).get("pages", {}).values())
        if "continue" not in veri:
            break
        devam = veri["continue"]
        time.sleep(ISTEK_ARASI)
    return uyeler[:limit]


def kategori_dosyalari(
    oturum: requests.Session, kategori: str, limit: int, derinlik: int = 2
) -> list[dict]:
    """Kategorideki dosyaları toplar; gerekirse alt kategorilere iner.

    Üst kategoriler (ör. "Earthquakes in Turkey") doğrudan dosya içermez,
    yalnızca alt kategori barındırır; özyineleme olmadan sıfır görüntüyle
    dönüyorlardı.
    """
    dosyalar = _uyeler(oturum, kategori, "file", limit)
    if len(dosyalar) >= limit or derinlik <= 0:
        return dosyalar[:limit]

    for alt in _uyeler(oturum, kategori, "subcat", 25):
        if len(dosyalar) >= limit:
            break
        try:
            dosyalar.extend(
                kategori_dosyalari(oturum, alt["title"], limit - len(dosyalar), derinlik - 1)
            )
        except RuntimeError as hata:
            print(f"\n    ⚠️ alt kategori atlandı: {alt['title'][:40]} — {hata}", end="")
        time.sleep(ISTEK_ARASI)
    return dosyalar[:limit]


def _kayit(sayfa: dict, kategori: Kategori) -> dict | None:
    """Commons sayfasını korpus kaydına çevirir; kullanılamazsa None."""
    bilgi = (sayfa.get("imageinfo") or [{}])[0]
    thumb = bilgi.get("thumburl")
    if not thumb or not bilgi.get("mime", "").startswith("image/"):
        return None

    ustveri = bilgi.get("extmetadata", {})

    def alan(ad: str) -> str | None:
        deger = ustveri.get(ad, {}).get("value")
        return deger.strip() if isinstance(deger, str) else None

    # Çekim tarihi varsa o, yoksa yükleme tarihi. "İlk kez ne zaman yayımlandı"
    # sorusunun cevabı budur ve yanlış bağlam kanıtının çekirdeğidir.
    tarih = alan("DateTimeOriginal") or bilgi.get("timestamp", "")
    return {
        "baslik": sayfa.get("title", ""),
        "olay": kategori.olay,
        "konum": kategori.konum,
        "kategori": kategori.ad,
        "ilk_yayin": tarih[:40] if tarih else None,
        "kaynak_url": bilgi.get("descriptionurl"),
        "thumb_url": thumb,
        "lisans": alan("LicenseShortName"),
        "yazar": alan("Artist"),
    }


def indir(oturum: requests.Session, kayit: dict, hedef: Path) -> bool:
    """Küçük boy görüntüyü indirir; başarısızsa False."""
    if hedef.exists():
        return True
    try:
        yanit = oturum.get(kayit["thumb_url"], timeout=60)
        yanit.raise_for_status()
        hedef.write_bytes(yanit.content)
        return True
    except Exception as hata:  # ağ hatası tüm toplamayı durdurmamalı
        print(f"    ⚠️ indirilemedi: {kayit['baslik'][:50]} — {type(hata).__name__}")
        return False


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--kategori-basina", type=int, default=250, help="kategori başına azami dosya")
    a.add_argument("--liste-only", action="store_true", help="indirme, yalnızca say")
    args = a.parse_args()

    oturum = _oturum()
    GORUNTU_DIZINI.mkdir(parents=True, exist_ok=True)

    kayitlar: list[dict] = []
    gorulen: set[str] = set()

    for kategori in KATEGORILER:
        print(f"→ {kategori.ad[:62]:64s} ", end="", flush=True)
        try:
            sayfalar = kategori_dosyalari(oturum, kategori.ad, args.kategori_basina)
        except Exception as hata:
            print(f"🔴 {type(hata).__name__}")
            continue

        eklenen = 0
        for sayfa in sayfalar:
            kayit = _kayit(sayfa, kategori)
            if kayit is None or kayit["baslik"] in gorulen:
                continue
            gorulen.add(kayit["baslik"])

            ad = f"{len(kayitlar):05d}.jpg"
            if not args.liste_only and not indir(oturum, kayit, GORUNTU_DIZINI / ad):
                continue
            kayit["dosya"] = ad
            kayitlar.append(kayit)
            eklenen += 1
        print(f"{eklenen:>4d} görüntü")

    if not args.liste_only:
        with KAYIT_DOSYASI.open("w", encoding="utf-8") as f:
            for k in kayitlar:
                f.write(json.dumps(k, ensure_ascii=False) + "\n")

    print(f"\n✓ {len(kayitlar):,} kayıt")
    olaylar: dict[str, int] = {}
    for k in kayitlar:
        olaylar[k["olay"]] = olaylar.get(k["olay"], 0) + 1
    for olay, sayi in sorted(olaylar.items(), key=lambda p: -p[1]):
        print(f"    {sayi:>5d}  {olay}")
    if not args.liste_only:
        print(f"\n  görüntüler: {GORUNTU_DIZINI.relative_to(REPO_ROOT)}")
        print(f"  üstveri   : {KAYIT_DOSYASI.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
