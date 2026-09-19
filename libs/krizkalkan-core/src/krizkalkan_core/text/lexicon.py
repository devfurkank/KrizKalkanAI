"""Türkçe kriz söylemi sözlüğü.

Rapor 3.1 · M3'te tanımlanan sekiz manipülatif söylem etiketi (Görev B1) ve
ayrı yürütülen yardım çağrısı sınıflandırıcısı (Görev B2) için desenler.

Desenler bilinçli olarak kök hâlinde tutulmuştur; Türkçe eklerin tamamını
listelemek yerine `normalize()` ile ek kırpması yapılır. Model eğitilene kadar
bu sözlük M3'ün yerine geçer ve aynı sözleşmeyi (etiket → skor) üretir.
"""

from __future__ import annotations

import re
import unicodedata

from krizkalkan_core.taxonomy import ManipulationLabel as L

# ─────────────────────── Normalizasyon ───────────────────────

#: Türkçe karakter bozulmalarını geri alır (rapor 3.2 · veri ön işleme).
_DEASCII = str.maketrans({"i": "i", "ı": "i", "İ": "i", "I": "i"})

_URL = re.compile(r"https?://\S+|www\.\S+")
_MENTION = re.compile(r"@\w+")
_NUM = re.compile(r"\d+[.,]?\d*")
_WS = re.compile(r"\s+")


#: Uzunluk koruyan katlama. Eşleşme konumları ham metne birebir eşlendiği için
#: iddia metni kullanıcıya özgün Türkçe yazımıyla gösterilebilir.
_FOLD = str.maketrans(
    "ÂâÇçĞğİıÎîÖöŞşÜüÛûÔô",
    "aaccggiiiioossuuuuoo",
)


def fold_aligned(text: str) -> str:
    """Aksanı düşürür ve küçük harfe indirir; karakter sayısını korur."""
    return text.translate(_FOLD).lower()


def normalize(text: str) -> str:
    """Karşılaştırma için metni sadeleştirir.

    Küçük harfe indirir, aksanı düşürür, URL/kullanıcı adlarını yer tutucuya
    çevirir. Sayılar korunur — büyüklük ve zaman ifadeleri için gereklidir.
    """
    t = text.casefold()
    t = _URL.sub(" <url> ", t)
    t = _MENTION.sub(" <kullanici> ", t)
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.translate(_DEASCII)
    return _WS.sub(" ", t).strip()


# ─────────────────────── Etiket desenleri ───────────────────────
# Her desen: (regex, ağırlık). Ağırlık, desenin etiketi ne kadar güçlü
# gösterdiğini ifade eder; birden fazla desen eşleşirse doygunlukla birleşir.

PATTERNS: dict[L, list[tuple[str, float]]] = {
    L.PANIK_YAYMA: [
        (r"herkes\s+kac", 0.55),
        (r"kacin\b|kaciniz\b", 0.45),
        (r"buyuk\s+felaket|facia|felaket\s+kapida", 0.50),
        (r"dehset|korkunc|vahim", 0.35),
        (r"sehri?\s+terk\s+ed", 0.60),
        (r"can\s+havliyle|panik\s+icinde", 0.35),
        (r"yok\s+olacak|yerle\s+bir", 0.45),
    ],
    L.KAYNAKSIZ_ACIL_CAGRI: [
        (r"acil\s+duyur", 0.55),
        (r"herkese\s+haber\s+ver", 0.55),
        (r"acilen\b", 0.35),
        (r"duyurun\b|yayin\b", 0.30),
        (r"herkes\s+bilsin", 0.45),
    ],
    # Kurum taklidi yalnızca ATIF biçiminde ("X açıkladı") aranır. Kurumun
    # kendi hesabından "resmî açıklamalarımız" demesi taklit değildir; bu
    # yüzden çıplak "resmi aciklama" deseni bilinçli olarak yoktur.
    L.KURUM_TAKLIDI: [
        (r"afad\s+(acikladi|duyurdu|bildirdi|uyardi)", 0.75),
        (r"valilik\s+(acikladi|duyurdu|bildirdi)", 0.70),
        (r"bakanlik\s+(acikladi|duyurdu|bildirdi)", 0.70),
        (r"akom\s+(acikladi|duyurdu)", 0.65),
        (r"kandilli\s+(acikladi|duyurdu)", 0.65),
        (r"yetkililer\s+(acikladi|duyurdu)", 0.45),
    ],
    L.YANLIS_KESINLIK: [
        (r"kesinlikle\b", 0.45),
        (r"kesin\s+bilgi", 0.60),
        (r"%\s*100|yuzde\s+yuz", 0.50),
        (r"netlesti\b|dogrulandi\b", 0.40),
        (r"su\s+an\s+kesin", 0.50),
        (r"suphe\s+yok", 0.45),
    ],
    L.TOPLUMSAL_KISKIRTMA: [
        (r"hesap\s+soral", 0.60),
        (r"sokaga\s+dokul", 0.70),
        (r"isyan\s+ed", 0.60),
        (r"linc\b", 0.55),
        (r"bunlarin\s+hepsi\s+suclu", 0.55),
        (r"aramizda\s+dusman", 0.50),
    ],
    L.ACILIYET_BASKISI: [
        (r"hemen\s+paylas", 0.70),
        (r"paylasmadan\s+gecme", 0.65),
        (r"vakit\s+kaybetme", 0.50),
        (r"gec\s+olmadan", 0.45),
        (r"silinmeden\s+once", 0.60),
        (r"hizlica\s+yay", 0.55),
    ],
    L.KOMPLO_CERCEVESI: [
        (r"medya\s+(gizliyor|susuyor|yazmiyor)", 0.75),
        (r"sansurl", 0.55),
        (r"size\s+soylemedik", 0.60),
        (r"gercekleri\s+sakl", 0.65),
        (r"kimse\s+konusmuyor", 0.45),
        (r"ortbas\s+ed", 0.55),
    ],
}

# ─────────────────────── Görev B2: yardım çağrısı ───────────────────────
# Kural 0'ı besleyen ayrı sınıflandırıcı. Eşik kasten düşüktür; bu yüzden
# desenler geniş tutulmuş, kapsam duyarlılık lehine genişletilmiştir.

HELP_CALL_PATTERNS: list[tuple[str, float]] = [
    (r"enkaz\s+alt", 0.85),
    (r"gockuk\s+alt|goc(uk)?\s+alt", 0.80),
    (r"yardim\s+ed(in|iniz)", 0.70),
    (r"kurtar(in|iniz|abilir)", 0.70),
    (r"sesimizi\s+duy", 0.75),
    (r"mahsur\s+kald", 0.80),
    (r"ulasam(iyoruz|adik)", 0.60),
    (r"kayip\b|kaybol", 0.50),
    (r"acil\s+yardim", 0.75),
    (r"ekip\s+gonder", 0.65),
    (r"adres\s*[:\-]", 0.55),
    (r"\bakrabam|\bkardesim|\bannem|\bbabam|\boglum|\bkizim", 0.35),
    (r"hala\s+ses\s+geliyor", 0.80),
    (r"kurtarma\s+ekib", 0.55),
]

#: Yardım çağrısını taklit eden ama dezenformasyon olan içerikleri ayırmak için
#: negatif işaretler. Skoru düşürür, sıfırlamaz — Kural 0 duyarlılık lehinedir.
HELP_CALL_NEGATIVES: list[tuple[str, float]] = [
    (r"hemen\s+paylas", 0.15),
    (r"medya\s+gizliyor", 0.20),
    (r"sokaga\s+dokul", 0.25),
]


# ─────────────────────── İddia çıkarımı desenleri ───────────────────────

CITIES = [
    "adana",
    "adiyaman",
    "afyon",
    "agri",
    "aksaray",
    "amasya",
    "ankara",
    "antalya",
    "ardahan",
    "artvin",
    "aydin",
    "balikesir",
    "bartin",
    "batman",
    "bayburt",
    "bilecik",
    "bingol",
    "bitlis",
    "bolu",
    "burdur",
    "bursa",
    "canakkale",
    "cankiri",
    "corum",
    "denizli",
    "diyarbakir",
    "duzce",
    "edirne",
    "elazig",
    "erzincan",
    "erzurum",
    "eskisehir",
    "gaziantep",
    "giresun",
    "gumushane",
    "hakkari",
    "hatay",
    "igdir",
    "isparta",
    "istanbul",
    "izmir",
    "kahramanmaras",
    "karabuk",
    "karaman",
    "kars",
    "kastamonu",
    "kayseri",
    "kilis",
    "kirikkale",
    "kirklareli",
    "kirsehir",
    "kocaeli",
    "konya",
    "kutahya",
    "malatya",
    "manisa",
    "mardin",
    "mersin",
    "mugla",
    "mus",
    "nevsehir",
    "nigde",
    "ordu",
    "osmaniye",
    "rize",
    "sakarya",
    "samsun",
    "sanliurfa",
    "siirt",
    "sinop",
    "sivas",
    "sirnak",
    "tekirdag",
    "tokat",
    "trabzon",
    "tunceli",
    "usak",
    "van",
    "yalova",
    "yozgat",
    "zonguldak",
]

#: Şehir adlarının görünen (Türkçe) karşılıkları — arayüzde gösterim için.
CITY_DISPLAY: dict[str, str] = {
    "adiyaman": "Adıyaman",
    "agri": "Ağrı",
    "aydin": "Aydın",
    "balikesir": "Balıkesir",
    "bingol": "Bingöl",
    "canakkale": "Çanakkale",
    "cankiri": "Çankırı",
    "corum": "Çorum",
    "diyarbakir": "Diyarbakır",
    "duzce": "Düzce",
    "elazig": "Elazığ",
    "eskisehir": "Eskişehir",
    "gumushane": "Gümüşhane",
    "igdir": "Iğdır",
    "istanbul": "İstanbul",
    "izmir": "İzmir",
    "kahramanmaras": "Kahramanmaraş",
    "karabuk": "Karabük",
    "kirikkale": "Kırıkkale",
    "kirklareli": "Kırklareli",
    "kirsehir": "Kırşehir",
    "kutahya": "Kütahya",
    "mugla": "Muğla",
    "mus": "Muş",
    "nevsehir": "Nevşehir",
    "nigde": "Niğde",
    "sanliurfa": "Şanlıurfa",
    "sirnak": "Şırnak",
    "sinop": "Sinop",
    "tekirdag": "Tekirdağ",
    "usak": "Uşak",
}


def city_display(slug: str) -> str:
    return CITY_DISPLAY.get(slug, slug.capitalize())


CLAIM_PATTERNS: dict[str, list[str]] = {
    "altyapı_hasarı": [
        r"baraj\s+(yikil|patla|cat)",
        r"kopru\s+(yikil|coktu)",
        r"yol\s+(kapandi|coktu)",
        r"bina\s+(yikil|coktu)",
        r"elektrik\s+kesil",
        r"su\s+kesil",
        r"dogalgaz\s+(patla|kesil)",
    ],
    "ikincil_afet_uyarısı": [
        r"ikinci\s+(buyuk\s+)?deprem",
        r"artci\s+bekleniyor",
        r"tsunami",
        r"daha\s+buyuk\s+deprem",
        r"sel\s+bekleniyor",
    ],
    "tahliye": [
        r"tahliye\s+edil",
        r"sehri?\s+terk",
        r"bosalt(in|iliyor)",
        r"guvenli\s+bolgeye",
    ],
    "can_kaybı": [
        r"can\s+kaybi",
        r"olu\s+sayisi",
        r"hayatini\s+kaybet",
        r"yarali\s+sayisi",
    ],
    "resmî_açıklama": [
        r"afad\s+aciklad",
        r"valilik\s+aciklad",
        r"bakanlik\s+aciklad",
        r"akom\s+duyur",
        # Kurumsal durum bildirimleri — resmî kaynakla doğrulanabilir ifadeler.
        r"arama\s+kurtarma",
        r"ekip(ler)?\s+sahada",
        r"calismalar\s+suruyor",
        r"yagis\s+uyarisi",
        r"sari\s+kod",
    ],
}

# ─────────────────────── Yalanlama (debunk) çerçevesi ───────────────────────
# Bilinen hata modu: bir tekzip metni, yalanladığı iddiayı alıntıladığı için
# dezenformasyon sanılır. Bu desenler metnin iddiayı ÖNE SÜRMEDİĞİNİ, aksine
# DÜZELTTİĞİNİ gösterir; füzyon katmanı bu durumda iddiayı kullanıcıya
# yüklemez.

DEBUNK_PATTERNS: list[tuple[str, float]] = [
    (r"gercegi\s+yansitmamakta", 0.90),
    (r"iddiasi\s+(asilsiz|dogru\s+degil)", 0.85),
    (r"asilsiz(dir)?\b", 0.70),
    (r"yalanla(ndi|nmistir|di)", 0.80),
    (r"tekzip", 0.85),
    (r"dogru\s+degildir", 0.75),
    (r"boyle\s+bir\s+(aciklama|uyari)\s+yap[il]?ma", 0.85),
    (r"dogrulanma(di|mistir)\b", 0.60),
    (r"bulunmadigini\s+bildir", 0.75),
]

MAGNITUDE = re.compile(r"\b(\d[.,]\d)\s*(?:buyuklug|siddet|magnitud)?", re.I)

TIME_EXPRESSIONS = [
    (r"az\s+once", "az önce"),
    (r"su\s+an|simdi", "şu an"),
    (r"birazdan|az\s+sonra", "az sonra"),
    (r"(\d+)\s*saat\s+icinde", "{0} saat içinde"),
    (r"(\d+)\s*dakika\s+icinde", "{0} dakika içinde"),
    (r"bu\s+gece", "bu gece"),
    (r"yarin", "yarın"),
]

ALLEGED_SOURCES = [
    (r"\bafad\b", "AFAD"),
    (r"\bvalilik\b", "Valilik"),
    (r"\bakom\b", "AKOM"),
    (r"\bkandilli\b", "Kandilli Rasathanesi"),
    (r"\bmgm\b|meteoroloji", "Meteoroloji Genel Müdürlüğü"),
    (r"bakanlik|bakanligi", "Bakanlık"),
    (r"belediye", "Belediye"),
]

CERTAINTY_ABSOLUTE = [r"kesinlikle", r"kesin\s+bilgi", r"%\s*100", r"netlesti", r"suphe\s+yok"]
CERTAINTY_RUMOUR = [r"duyduguma\s+gore", r"soyleniyor", r"iddiaya\s+gore", r"galiba", r"sanirim"]


def match_score(text: str, patterns: list[tuple[str, float]]) -> tuple[float, list[str]]:
    """Desen listesini uygular, doygunluklu birleşik skor ve eşleşmeleri döndürür.

    Birleştirme `1 - Π(1 - w)` biçimindedir: birden fazla zayıf işaret birikir
    ama skor asla 1'i aşmaz.
    """
    remaining = 1.0
    hits: list[str] = []
    for pattern, weight in patterns:
        m = re.search(pattern, text)
        if m:
            hits.append(m.group(0).strip())
            remaining *= 1.0 - weight
    return round(1.0 - remaining, 4), hits


# ─────────────────────────── Ağız normalizasyonu ───────────────────────────

#: Yaygın ağız çekimlerini ölçünlü biçime yaklaştıran kurallar.
#:
#: Adalet denetimi (docs/metrikler/adalet.md) ölçünlü Türkçe dışında yazan
#: kullanıcıların provokatif içerikte YARI oranda korunduğunu gösterdi: tespit
#: ölçünlü Türkçe'de 0,25 iken Karadeniz/Ege/gençlik dilinde 0,125. Desenler
#: kök üzerinde eşleştiği için sorun kökte değil çekimde; bu kurallar yalnızca
#: çekimi düzeltir, kökü değiştirmez.
#:
#: Şimdiki zaman eki ünlü uyumuna göre seçilir: kökün son ünlüsü kalınsa
#: "-uyor", inceyse "-iyor". Uyumu gözetmeyen sabit eşleme "konuşmayr"ı
#: "konusmiyor" yapıyor ve desen yine tutmuyordu.
DUZ_AGIZ_KURALLARI: tuple[tuple[str, str], ...] = (
    (r"iyo\b", "iyor"),
    (r"uyo\b", "uyor"),
    (r"elum\b", "elim"),
    (r"alum\b", "alim"),
    (r"umuz\b", "imiz"),
    (r"imuz\b", "imiz"),
    (r"sun\b", "sin"),
    (r"duk\b", "dik"),
    (r"tuk\b", "tik"),
    (r"nuz\b", "niz"),
    (r"lek\b", "lelim"),
    (r"cunki\b", "cunku"),
    (r"iler\b", "ilar"),
)

#: Kalın ünlüler — şimdiki zaman ekinin biçimini belirler.
KALIN_UNLULER = "aiou"

#: "-ayr/-eyr" biçimindeki şimdiki zaman: kök + ek olarak yakalanır.
_SIMDIKI = re.compile(r"(\w+?)[ae]yr(ler|lar)?\b")

_DUZ_DERLENMIS = tuple((re.compile(d), y) for d, y in DUZ_AGIZ_KURALLARI)


def _simdiki_zaman(eslesme: re.Match[str]) -> str:
    """Ağız şimdiki zamanını ünlü uyumuna göre ölçünlü biçime çevirir."""
    kok, cogul = eslesme.group(1), eslesme.group(2)
    unluler = [k for k in kok if k in "aeiou"]
    ek = "uyor" if unluler and unluler[-1] in KALIN_UNLULER else "iyor"
    return kok + ek + ("lar" if cogul else "")


def agiz_normalize(metin: str) -> str:
    """Katlanmış metni ağız çekimlerinden arındırır.

    `normalize()` çıktısı üzerinde çalışır. Uzunluğu değiştirdiği için kanıt
    konumları bu biçimden ÜRETİLEMEZ; yalnızca skorlama için kullanılır.
    """
    n = _SIMDIKI.sub(_simdiki_zaman, normalize(metin))
    for desen, yerine in _DUZ_DERLENMIS:
        n = desen.sub(yerine, n)
    return n
