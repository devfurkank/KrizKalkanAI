#!/usr/bin/env python
"""Depo bütünlüğü denetimi — kaynak dosyalar gerçekten depoda mı?

Yakaladığı hata sınıfı: `.gitignore` içindeki sabitlenmemiş bir desenin kaynak
kodu sessizce depodan silmesi. Bu bir kez yaşandı — `models/` deseni her
seviyedeki `models` dizinini yok saydığı için `krizkalkan_core/models` paketi
hiç commit edilmedi. Testler yerelde geçtiği için fark edilmedi; hata ancak
temiz bir klonda, başka bir makinede ortaya çıktı.

Denetim iki soruyu sorar:

    1. Kaynak ağaçlarındaki hiçbir dosya `.gitignore` tarafından yok sayılıyor mu?
    2. Her Python paketinin __init__.py'si depoda mı?

Kullanım: python scripts/ci/repo_denetimi.py
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Kaynak kodu barındıran ağaçlar — buradaki hiçbir dosya yok sayılamaz.
KAYNAK_AGACLARI = (
    "libs/krizkalkan-core/src",
    "libs/krizkalkan-core/tests",
    "apps/api/src",
    "apps/api/tests",
    "apps/worker/src",
    "apps/worker/tests",
    "apps/web/src",
    "packages/types/src",
    "scripts",
    "notebooks",
)

#: Denetlenecek uzantılar.
UZANTILAR = {".py", ".ts", ".tsx", ".json", ".ipynb", ".md", ".toml", ".yml", ".yaml"}

#: Bilinçli olarak üretilen ve yok sayılan dosyalar.
BEKLENEN_ISTISNALAR = {"apps/web/next-env.d.ts"}


def yok_sayilanlar(yollar: list[Path]) -> dict[str, str]:
    """`git check-ignore` ile yok sayılan dosyaları ve gerekçelerini döndürür."""
    if not yollar:
        return {}
    sonuc = subprocess.run(
        ["git", "check-ignore", "-v", "--stdin"],
        input="\n".join(str(y) for y in yollar),
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    bulgular: dict[str, str] = {}
    for satir in sonuc.stdout.splitlines():
        # biçim: <kaynak>:<satır>:<desen>\t<yol>
        parcalar = satir.split("\t")
        if len(parcalar) == 2:
            bulgular[parcalar[1]] = parcalar[0]
    return bulgular


def izlenmeyenler(yollar: list[Path]) -> list[str]:
    """Yok sayılmadığı hâlde depoya hiç eklenmemiş dosyalar."""
    izlenen = set(
        subprocess.run(
            ["git", "ls-files"], capture_output=True, text=True, cwd=REPO_ROOT, check=True
        ).stdout.splitlines()
    )
    return [str(y) for y in yollar if str(y) not in izlenen]


def main() -> int:
    yollar: list[Path] = []
    for agac in KAYNAK_AGACLARI:
        kok = REPO_ROOT / agac
        if not kok.exists():
            continue
        for yol in kok.rglob("*"):
            if not yol.is_file() or yol.suffix not in UZANTILAR:
                continue
            if any(p in {"__pycache__", "node_modules", ".next", ".venv"} for p in yol.parts):
                continue
            yollar.append(yol.relative_to(REPO_ROOT))

    print(f"→ {len(yollar)} kaynak dosya denetleniyor")

    hata = 0

    yoksayilan = {
        y: gerekce for y, gerekce in yok_sayilanlar(yollar).items() if y not in BEKLENEN_ISTISNALAR
    }
    if yoksayilan:
        hata = 1
        print("\n🔴 Kaynak dosyalar .gitignore tarafından yok sayılıyor:\n")
        for yol, gerekce in sorted(yoksayilan.items()):
            print(f"   {yol}\n     ← {gerekce}")
        print(
            "\n   Desen muhtemelen sabitlenmemiş. Depo kökündeki bir dizini kastediyorsa"
            "\n   başına eğik çizgi koyun: `models/` yerine `/models/`."
        )

    eksik = [
        y for y in izlenmeyenler(yollar) if y not in yoksayilan and y not in BEKLENEN_ISTISNALAR
    ]
    if eksik:
        hata = 1
        print("\n🔴 Depoya eklenmemiş kaynak dosyalar:\n")
        for yol in sorted(eksik):
            print(f"   {yol}")

    if not hata:
        print("✓ Tüm kaynak dosyalar depoda ve yok sayılmıyor")
    return hata


if __name__ == "__main__":
    raise SystemExit(main())
