# KrizKalkan AI

Afet ve kriz dönemlerinde paylaşılan video, ses ve metin içeriklerini çok modlu yapay zekâ ile
analiz ederek; içeriğin **sentetik mi, manipüle mi, yanlış bağlamda mı, yoksa yalnızca
doğrulanmamış mı** olduğunu birbirinden ayıran, kararını **kanıtlarla** açıklayan ve **hiçbir
içeriği silmeden** kademeli bağlam kazandıran Türkçe odaklı bilgi bütünlüğü altyapısı.

> TEKNOFEST 2026 · NSosyal İnovasyon Yarışması · Tematik alan: **Sosyal Yapay Zekâ**

---

## Depo yapısı

```
KrizKalkanAI/
├── apps/
│   ├── web/                  Next.js 16 · içerik akışı, analiz kartı, moderatör paneli, kriz radar
│   ├── api/                  FastAPI · ağ geçidi, içerik alımı, moderasyon API'si
│   └── worker/               Celery · analiz kuyruğu işçisi
├── libs/
│   └── krizkalkan-core/      Paylaşılan alan modeli ve analiz modülleri (M1–M7)
├── packages/
│   ├── types/                Paylaşılan TypeScript tip sözleşmeleri
│   └── config/               Paylaşılan tsconfig temeli
├── infra/
│   └── compose.yaml          PostgreSQL · Redis · MinIO
├── data/                     Veri dizini (içeriği commit edilmez)
├── docs/                     Mimari, veri envanteri, model kartları, etik protokol
├── notebooks/                Keşifsel analiz
└── scripts/                  Bakım ve veri betikleri
```

### Analiz modülleri

| Kod | Modül | Paket |
| --- | --- | --- |
| M1 | Köken ve yeniden-bağlam tespiti | `krizkalkan_core.provenance` |
| M2 | Çok modlu çelişki analizi | `krizkalkan_core.multimodal` |
| M3 | Türkçe kriz metin motoru | `krizkalkan_core.text` |
| M4 | Sentetik medya sinyalleri | `krizkalkan_core.synthetic` |
| M5 | Doğrulanmış kriz bilgi havuzu | `krizkalkan_core.knowledge` |
| M6 | Kalibre kanıt füzyonu | `krizkalkan_core.fusion` |
| M7 | Kademeli müdahale politikası | `krizkalkan_core.policy` |

---

## Teknoloji yığını

| Katman | Teknoloji | Sürüm |
| --- | --- | --- |
| Web | Next.js · React · TypeScript · Tailwind CSS | 16.3.1 · 19.2.8 · 5.9 · 4.1 |
| API | FastAPI · Uvicorn · Pydantic | 0.141 · 0.52 · 2.13 |
| Kuyruk | Celery · Redis | 5.6 · 8 |
| Veritabanı | PostgreSQL · SQLAlchemy · Alembic | 18 · 2.0 · 1.17 |
| Nesne depolama | MinIO (S3 uyumlu) | latest |
| Çalışma zamanı | Node.js · Python | 24 (LTS) · 3.12 |
| Paket yönetimi | pnpm workspaces · pip (PEP 621) | 11.16 |

---

## Kurulum

### Gereksinimler

- Node.js 24+ ve pnpm 11+
- Python 3.12
- Docker (altyapı servisleri için)

### Adımlar

```bash
cp .env.example .env
make setup      # Node + Python bağımlılıkları
make up         # PostgreSQL, Redis, MinIO
```

### Geliştirme sunucuları

Her biri ayrı bir terminalde:

```bash
make dev-web      # http://localhost:3000
```

```bash
make dev-api      # http://localhost:8000  ·  dokümantasyon: /docs
```

```bash
make dev-worker
```

### Test ve kalite

```bash
make test
```

```bash
make lint
```

---

## Katkı kuralları

- Dal (branch) adları: `feat/...`, `fix/...`, `docs/...`, `data/...`
- Her modül kendi alt paketinde geliştirilir; modüller arası bağımlılık `krizkalkan_core.schemas`
  üzerinden kurulur.
- Veri dosyaları, model ağırlıkları ve `.env` **hiçbir koşulda** commit edilmez.
- Yüz ve ses verisi işleyen kod, `docs/etik-protokol.md` kurallarına tabidir.
