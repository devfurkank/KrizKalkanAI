.PHONY: help setup setup-node setup-python setup-models model-durum up down logs demo dev-web dev-api dev-worker test lint format clean

PY := python3.12
VENV := .venv

help:
	@echo "KrizKalkan AI — kullanılabilir komutlar:"
	@echo "  make demo         SUNUM: API + arayüzü birlikte başlatır"
	@echo "  make setup        Tüm bağımlılıkları kurar (Node + Python)"
	@echo "  make setup-models Çıkarım bağımlılıklarını kurar (ONNX, FAISS, sklearn)"
	@echo "  make model-durum  Yüklü model ağırlıklarını ve çalışma zamanını gösterir"
	@echo "  make up           Altyapıyı başlatır (Postgres, Redis, MinIO)"
	@echo "  make down         Altyapıyı durdurur"
	@echo "  make dev-web      Next.js geliştirme sunucusu (:3000)"
	@echo "  make dev-api      FastAPI geliştirme sunucusu (:8000)"
	@echo "  make dev-worker   Celery işçisi"
	@echo "  make test         Tüm testleri çalıştırır"
	@echo "  make lint         Lint kontrolü"
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

lint:
	$(VENV)/bin/ruff check .
	pnpm -r --parallel lint

format:
	$(VENV)/bin/ruff format .
	pnpm format

clean:
	rm -rf $(VENV) node_modules apps/web/node_modules apps/web/.next
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
