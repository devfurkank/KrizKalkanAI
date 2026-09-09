"""M4 · C2PA köken üstverisi doğrulaması.

Diğer M4 sinyalleri olasılıksaldır; bu değildir. İmza kriptografik bir kayıttır
ve testler bunu gerçek bir imzalı dosya üzerinde doğrular — sahte bir okuyucuyla
değil. Sertifika zinciri ve imzalı görüntü test sırasında üretilir; hiçbir ikili
dosya depoya girmez.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from krizkalkan_core.synthetic.c2pa import C2paDurum, dogrula

c2pa = pytest.importorskip("c2pa", reason="c2pa paketi kurulu değil")

#: C2PA kendinden imzalı sertifikayı reddeder; iki katmanlı zincir gerekir.
LEAF_CNF = """[req]
distinguished_name=dn
[dn]
[v3]
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature
extendedKeyUsage=critical,emailProtection
"""

AI_KAYNAK = "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"


def _openssl(*args: str, cwd: Path) -> None:
    subprocess.run(["openssl", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture(scope="module")
def imzali_goruntu(tmp_path_factory) -> Path:
    """C2PA ile "yapay zekâ üretimi" olarak imzalanmış bir JPEG üretir."""
    if shutil.which("openssl") is None:
        pytest.skip("openssl bulunamadı")

    dizin = tmp_path_factory.mktemp("c2pa")
    (dizin / "leaf.cnf").write_text(LEAF_CNF, encoding="utf-8")

    _openssl(
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-keyout",
        "ca_key.pem",
        "-out",
        "ca_cert.pem",
        "-days",
        "365",
        "-nodes",
        "-subj",
        "/CN=KrizKalkan Test CA/O=KrizKalkan",
        "-addext",
        "basicConstraints=critical,CA:TRUE,pathlen:0",
        "-addext",
        "keyUsage=critical,keyCertSign,cRLSign",
        cwd=dizin,
    )
    _openssl(
        "req",
        "-new",
        "-newkey",
        "rsa:2048",
        "-keyout",
        "leaf_key.pem",
        "-out",
        "leaf.csr",
        "-nodes",
        "-subj",
        "/CN=KrizKalkan Signer/O=KrizKalkan",
        cwd=dizin,
    )
    _openssl(
        "x509",
        "-req",
        "-in",
        "leaf.csr",
        "-CA",
        "ca_cert.pem",
        "-CAkey",
        "ca_key.pem",
        "-CAcreateserial",
        "-out",
        "leaf_cert.pem",
        "-days",
        "365",
        "-extfile",
        "leaf.cnf",
        "-extensions",
        "v3",
        cwd=dizin,
    )
    (dizin / "zincir.pem").write_bytes(
        (dizin / "leaf_cert.pem").read_bytes() + (dizin / "ca_cert.pem").read_bytes()
    )

    pil = pytest.importorskip("PIL.Image", reason="Pillow kurulu değil")
    girdi = dizin / "girdi.jpg"
    pil.new("RGB", (320, 240), (120, 90, 60)).save(girdi, "JPEG")

    manifest = {
        "claim_generator": "KrizKalkanTest/0.1",
        "title": "sentetik test görüntüsü",
        "assertions": [
            {
                "label": "c2pa.actions",
                "data": {"actions": [{"action": "c2pa.created", "digitalSourceType": AI_KAYNAK}]},
            }
        ],
    }
    imzaci = c2pa.Signer.from_info(
        c2pa.C2paSignerInfo(
            alg=b"ps256",
            sign_cert=(dizin / "zincir.pem").read_bytes(),
            private_key=(dizin / "leaf_key.pem").read_bytes(),
            ta_url=None,
        )
    )
    hedef = dizin / "imzali.jpg"
    try:
        with (
            c2pa.Builder(json.dumps(manifest)) as olusturucu,
            girdi.open("rb") as gir,
            hedef.open("wb") as cik,
        ):
            olusturucu.sign(imzaci, "image/jpeg", gir, cik)
    except Exception as hata:  # imzalama ortama bağlıdır
        pytest.skip(f"C2PA imzalama başarısız: {type(hata).__name__}")
    return hedef


def test_ai_imzasi_dogrulanir(imzali_goruntu: Path) -> None:
    """İmzalı AI içeriği tahmin edilmez, DOĞRULANIR."""
    sonuc = dogrula(imzali_goruntu)

    assert sonuc.durum is C2paDurum.AI_IMZALI
    assert not sonuc.cekinmeli
    assert sonuc.skor > 0.9
    assert sonuc.dijital_kaynak is not None
    assert sonuc.dijital_kaynak.endswith("trainedAlgorithmicMedia")


def test_surumlu_assertion_etiketi_yakalanir(imzali_goruntu: Path) -> None:
    """Assertion etiketi sürüm eki taşır (c2pa.actions.v2); önek eşleşmeli.

    Tam eşleşme kullanıldığında imzalı AI görüntüsü sessizce "imza yok"
    sayılıyordu — sinyal hiç üretilmiyordu.
    """
    import c2pa as _c2pa

    with _c2pa.Reader(str(imzali_goruntu)) as okuyucu:
        ham = json.loads(okuyucu.json())
    aktif = ham["manifests"][ham["active_manifest"]]
    etiketler = [a.get("label", "") for a in aktif.get("assertions", [])]

    assert any(e.startswith("c2pa.actions") for e in etiketler)
    assert dogrula(imzali_goruntu).durum is C2paDurum.AI_IMZALI


def test_imzasiz_dosya_cekinir(tmp_path: Path) -> None:
    """İmza yokluğu içerik hakkında hiçbir şey söylemez."""
    pil = pytest.importorskip("PIL.Image")
    yol = tmp_path / "imzasiz.jpg"
    pil.new("RGB", (64, 64), (10, 10, 10)).save(yol, "JPEG")

    sonuc = dogrula(yol)
    assert sonuc.durum is C2paDurum.IMZA_YOK
    assert sonuc.cekinmeli, "imza yokluğu karara girmemeli"
    assert sonuc.skor == 0.0


def test_olmayan_dosya_istisna_firlatmaz(tmp_path: Path) -> None:
    """Köken üstverisi yardımcı sinyaldir; okunamaması analizi durdurmamalı."""
    assert dogrula(tmp_path / "yok.jpg").durum is C2paDurum.IMZA_YOK


def test_bozuk_dosya_istisna_firlatmaz(tmp_path: Path) -> None:
    yol = tmp_path / "bozuk.jpg"
    yol.write_bytes(b"bu bir jpeg degil")
    assert dogrula(yol).durum is C2paDurum.IMZA_YOK


def test_imzali_icerik_sentetik_siniflanir(imzali_goruntu: Path) -> None:
    """Uçtan uca: imzalı AI görüntüsü SENTETİK_MEDYA olarak sınıflanır."""
    from krizkalkan_core.pipeline import AnalysisPipeline
    from krizkalkan_core.taxonomy import Verdict

    sonuc = AnalysisPipeline().analyse(
        body="Bu görüntü afet bölgesinden.",
        media_kind="image",
        media_fingerprint=str(imzali_goruntu),
    )
    assert sonuc.verdict is Verdict.SENTETIK_MEDYA
    assert sonuc.confidence > 0.8
