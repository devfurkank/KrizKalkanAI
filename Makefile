.PHONY: help setup setup-node setup-python setup-models model-durum veri m5-index depo-denetimi up down logs demo dev-web dev-api dev-worker test lint format clean m4-video m4-video-aktar

PY := python3.12
VENV := .venv

help:
	@echo "KrizKalkan AI — kullanılabilir komutlar:"
	@echo "  make demo         SUNUM: API + arayüzü birlikte başlatır"
	@echo "  make setup        Tüm bağımlılıkları kurar (Node + Python)"
	@echo "  make setup-models Çıkarım bağımlılıklarını kurar (ONNX, FAISS, sklearn)"
	@echo "  make model-durum  Yüklü model ağırlıklarını ve çalışma zamanını gösterir"
	@echo "  make veri         Veri kümelerini indirir, uyumlaştırır, böler"
	@echo "  make m5-index     M5 bilgi havuzunu ve geri getirme indeksini kurar"
	@echo "  make m4-model     M4 sentetik görüntü detektörlerini kurar (DeepReality → ONNX)"
	@echo "  make m4-video     M4 video kümesinin manifestini ve ölçümünü üretir (kabul kapısı)"
	@echo "  make m4-video-aktar M4 video ağırlığını ONNX'e aktarır (ayrı ortamda TensorFlow kurar)"
	@echo "  make up           Altyapıyı başlatır (Postgres, Redis, MinIO)"
	@echo "  make down         Altyapıyı durdurur"
	@echo "  make dev-web      Next.js geliştirme sunucusu (:3000)"
	@echo "  make dev-api      FastAPI geliştirme sunucusu (:8000)"
	@echo "  make dev-worker   Celery işçisi"
	@echo "  make test         Tüm testleri çalıştırır"
	@echo "  make lint         Lint kontrolü"
	@echo "  make depo-denetimi Kaynak dosyalar depoda mı? (.gitignore tuzakları)"
	@echo "  make format       Kod biçimlendirme"

setup: setup-node setup-python
	@echo "Kurulum tamamlandı."

setup-node:
	pnpm install

setup-python:
	$(PY) -m venv $(VENV)
	$(VENV)/bin/python -m pip install --upgrade pip
	$(VENV)/bin/pip install -e "libs/krizkalkan-core[dev]"
	$(VENV)/bin/pip install -e "apps/api[dev]"
	$(VENV)/bin/pip install -e "apps/worker[dev]"

setup-models:
	$(VENV)/bin/pip install -e "libs/krizkalkan-core[models]"
	@echo "Çıkarım bağımlılıkları kuruldu. Ağırlıklar: python scripts/data/fetch_weights.py"

# Ağırlık dizininin ve çalışma zamanının durumunu raporlar.
# Sunum öncesi son kontrol komutu budur.
model-durum:
	@$(VENV)/bin/python -c "from krizkalkan_core.models import describe, registry; \
	import krizkalkan_core.pipeline; import json; \
	print(json.dumps(describe(), ensure_ascii=False, indent=2)); \
	print(json.dumps(registry.report(), ensure_ascii=False, indent=2))"

# Metin veri kümeleri: indirme → şema doğrulama → uyumlaştırma → olay bazlı bölme
veri:
	$(VENV)/bin/python scripts/data/fetch_text.py
	$(VENV)/bin/python scripts/data/harmonize.py

# M5: DMM havuzu (JSONL) + int8 ONNX kodlayıcı + gömme indeksi.
# Ağırlıklar commit edilmez; bu komut onları yeniden üretir.
m5-index:
	$(VENV)/bin/python scripts/data/build_knowledge.py
	$(VENV)/bin/python scripts/data/build_index.py

# M4: DeepReality ağırlıkları → int8 ONNX detektörler.
# Kaynak dizin KK_DEEPREALITY_DIR ile verilir; ağırlıklar commit edilmez.
# Kabul kapısı ölçümle açılır: scripts/eval/m4_synthetic.py
m4-model:
	$(VENV)/bin/python scripts/data/build_synthetic.py

# M4 video: küme manifesti + ölçüm. Ölçüm model kartını yazar; kabul kapısı
# (alan_ici_ozgulluk) bu kartı okur. Ağırlık models/m4_video altında olmalıdır.
m4-video:
	$(VENV)/bin/python scripts/data/build_video_afet.py
	$(VENV)/bin/python scripts/eval/m4_video.py

# M4 video: Keras ağırlığı → ONNX. TensorFlow yalnızca bu adımda gerekir ve demo
# ortamına girmez; ayrı bir sanal ortama kurulur. Aktarım kartı sıfırlar,
# ardından `make m4-video` çalıştırılmalıdır.
m4-video-aktar:
	$(PY) -m venv .venv-aktar
	.venv-aktar/bin/pip install -e "libs/krizkalkan-core[models,video-export]"
	.venv-aktar/bin/python scripts/train/m4_video_disa_aktar.py

up:
	docker compose -f infra/compose.yaml up -d

down:
	docker compose -f infra/compose.yaml down

logs:
	docker compose -f infra/compose.yaml logs -f

# Sunum komutu: analiz servisi ve arayüz birlikte ayağa kalkar.
# Postgres/Redis/MinIO gerekmez — depo bellek içi, analiz satır içi çalışır.
demo:
	@echo "→ API  : http://localhost:8000/docs"
	@echo "→ Arayüz: http://localhost:3000"
	@$(VENV)/bin/uvicorn krizkalkan_api.main:app --port 8000 & \
	 pnpm --filter @krizkalkan/web dev; \
	 kill %1 2>/dev/null || true

dev-web:
	pnpm --filter @krizkalkan/web dev

dev-api:
	$(VENV)/bin/uvicorn krizkalkan_api.main:app --reload --port 8000

dev-worker:
	$(VENV)/bin/celery -A krizkalkan_worker.app:celery_app worker --loglevel=info

test:
	$(VENV)/bin/pytest

# Kaynak kodun .gitignore tarafından sessizce silinmediğini doğrular.
depo-denetimi:
	$(VENV)/bin/python scripts/ci/repo_denetimi.py

lint: depo-denetimi
	$(VENV)/bin/ruff check .
	pnpm -r --parallel lint

format:
	$(VENV)/bin/ruff format .
	pnpm format

clean:
	rm -rf $(VENV) node_modules apps/web/node_modules apps/web/.next
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
