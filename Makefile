# Geo-Adaptive Energy Assistant Makefile
.PHONY: help dev test build deploy clean lint format

# Default target
help:
	@echo "Available targets:"
	@echo "  dev          - Set up development environment"
	@echo "  test         - Run all tests"
	@echo "  build        - Build Docker images"
	@echo "  deploy       - Deploy to staging"
	@echo "  clean        - Clean up build artifacts"
	@echo "  lint         - Run linting"
	@echo "  format       - Format code"

# Development environment setup
dev:
	python -m venv venv
	. venv/bin/activate && pip install -r requirements.txt
	. venv/bin/activate && pre-commit install
	@echo "Development environment ready. Activate with: source venv/bin/activate"

# Testing
test:
	pytest tests/ -v --cov=services --cov=apps

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

test-e2e:
	pytest tests/e2e/ -v

test-rag:
	pytest tests/rag_eval/ -v

test-load:
	k6 run tests/load/load_test.js

# Code quality
lint:
	ruff check .
	mypy services/ apps/

format:
	black .
	ruff format .

# Build
build:
	docker build -t geo-energy-assistant:latest .

build-services:
	docker build -f services/api-gateway/Dockerfile -t api-gateway:latest services/api-gateway/
	docker build -f services/ingest/Dockerfile -t ingest-service:latest services/ingest/
	docker build -f services/normalize/Dockerfile -t normalize-service:latest services/normalize/
	docker build -f services/research-orchestrator/Dockerfile -t research-orchestrator:latest services/research-orchestrator/

# Deployment
deploy-staging:
	kubectl apply -f infra/k8s/staging/
	helm upgrade --install geo-energy-assistant infra/k8s/helm/ --namespace staging

deploy-prod:
	kubectl apply -f infra/k8s/production/
	helm upgrade --install geo-energy-assistant infra/k8s/helm/ --namespace production

# Infrastructure
infra-plan:
	cd infra/terraform && terraform plan

infra-apply:
	cd infra/terraform && terraform apply

# Cleanup
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	docker system prune -f

# Database migrations
db-migrate:
	alembic upgrade head

db-revision:
	alembic revision --autogenerate -m "$(MSG)"

# Local development servers
run-api:
	cd apps/api-gateway && uvicorn main:app --reload --host 0.0.0.0 --port 8000

run-explorer:
	cd apps/explorer-ui && npm run dev

run-radar:
	cd apps/radar-ui && npm run dev