"""İskelet doğrulama testi."""

import krizkalkan_core


def test_paket_yuklenebiliyor() -> None:
    assert krizkalkan_core.__version__ == "0.0.1"
