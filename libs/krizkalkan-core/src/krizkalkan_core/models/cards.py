"""Model kartları — üretim ve okuma.

Rapor 3.2, her model için amaç, veri, yordam, ölçüm ve **bilinen sınırlar**
bilgisini talep eder. Bu bilgi elle yazılan bir metin değil, ağırlıkla birlikte
taşınan yapılandırılmış bir kayıttır: her eğitim koşusu `kart.json` üretir,
`scripts/eval/run_all.py` bunları `docs/model-kartlari/` altına markdown olarak
yazar. Böylece kart ile ağırlık asla birbirinden ayrı düşmez.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

#: Kartın ağırlık dizinindeki dosya adı.
CARD_FILENAME = "kart.json"


@dataclass(slots=True)
class Measurement:
    """Tek bir ölçüm — n değeri ve küme adı zorunludur.

    `n` ve `dataset` alanlarının zorunluluğu bilinçlidir: jürinin ilk sorusu
    "bu sayı hangi kümede, kaç örnekle?" olacaktır ve cevabın metrikle aynı
    yerde durması gerekir.
    """

    metric: str
    value: float
    dataset: str
    n: int
    note: str | None = None


@dataclass(slots=True)
class ModelCard:
    """Bir model sürümünün tam künyesi."""

    name: str
    module: str
    title: str
    version: str
    base_model: str
    purpose: str

    training_data: list[str] = field(default_factory=list)
    training_procedure: str = ""
    hyperparameters: dict[str, str | float | int] = field(default_factory=dict)
    split_strategy: str = "Olay bazlı bölünme (rastgele değil)"

    measurements: list[Measurement] = field(default_factory=list)
    known_limits: list[str] = field(default_factory=list)
    ethical_notes: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)

    license: str = "Proprietary"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    git_commit: str | None = None

    # ────────────────────────── giriş/çıkış ──────────────────────────

    def save(self, directory: Path) -> Path:
        """Kartı ağırlık dizinine JSON olarak yazar."""
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / CARD_FILENAME
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, directory: Path) -> ModelCard | None:
        """Ağırlık dizinindeki kartı okur; yoksa None."""
        path = directory / CARD_FILENAME
        if not path.exists():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["measurements"] = [Measurement(**m) for m in raw.get("measurements", [])]
        return cls(**raw)

    # ────────────────────────── markdown ──────────────────────────

    def to_markdown(self) -> str:
        """Rapora ve depoya konacak model kartı metnini üretir."""
        lines = [
            f"# {self.module} — {self.title} `v{self.version}`",
            "",
            "| | |",
            "|---|---|",
            f"| Model adı | `{self.name}` |",
            f"| Temel model | {self.base_model} |",
            f"| Sürüm | {self.version} |",
            f"| Oluşturulma | {self.created_at} |",
            f"| Git commit | `{self.git_commit or '—'}` |",
            f"| Lisans | {self.license} |",
            "",
            "## Amaç ve kapsam",
            "",
            self.purpose,
            "",
            "## Eğitim verisi",
            "",
        ]
        lines += [f"- {item}" for item in self.training_data] or ["- (belirtilmedi)"]
        lines += ["", "## Eğitim yordamı", "", self.training_procedure or "(belirtilmedi)", ""]

        if self.hyperparameters:
            lines += ["### Hiperparametreler", "", "| Parametre | Değer |", "|---|---|"]
            lines += [f"| {k} | {v} |" for k, v in self.hyperparameters.items()]
            lines += [""]

        lines += [f"**Bölünme stratejisi:** {self.split_strategy}", "", "## Ölçümler", ""]
        if self.measurements:
            lines += [
                "| Metrik | Değer | Değerlendirme kümesi | n | Not |",
                "|---|---|---|---|---|",
            ]
            lines += [
                f"| {m.metric} | {m.value:.4g} | {m.dataset} | {m.n} | {m.note or '—'} |"
                for m in self.measurements
            ]
        else:
            lines += ["> Henüz ölçüm yapılmadı."]

        lines += ["", "## Bilinen sınırlar", ""]
        lines += [f"- {item}" for item in self.known_limits] or [
            "- ⚠ Bu bölüm doldurulmadı. Model kartı, sınırları yazılmadan tamamlanmış sayılmaz."
        ]

        if self.ethical_notes:
            lines += ["", "## Etik değerlendirme", ""]
            lines += [f"- {item}" for item in self.ethical_notes]

        if self.out_of_scope:
            lines += ["", "## Kullanılmaması gereken durumlar", ""]
            lines += [f"- {item}" for item in self.out_of_scope]

        lines += [
            "",
            "---",
            "",
            "*Bu kart `scripts/eval/run_all.py` tarafından üretilmiştir; elle düzenlenmez.*",
            "",
        ]
        return "\n".join(lines)

    def write_markdown(self, docs_dir: Path) -> Path:
        docs_dir.mkdir(parents=True, exist_ok=True)
        path = docs_dir / f"{self.name.replace('_', '-')}.md"
        path.write_text(self.to_markdown(), encoding="utf-8")
        return path
