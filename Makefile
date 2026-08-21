.PHONY: help setup setup-node setup-python up down logs dev-web dev-api dev-worker test lint format clean

PY := python3.12
VENV := .venv

help:
	@echo "KrizKalkan AI — kullanılabilir komutlar:"
	@echo "  make setup        Tüm bağımlılıkları kurar (Node + Python)"
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

up:
	docker compose -f infra/compose.yaml up -d

down:
	docker compose -f infra/compose.yaml down

logs:
	docker compose -f infra/compose.yaml logs -f

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
