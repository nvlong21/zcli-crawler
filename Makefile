.PHONY: help install sync run run-prod test test-cov lint format check check-all migrate makemigrations migrate-down generate-grpc clean build docker-build docker-run docker-stop docker-logs docker-compose-up docker-compose-down

# Variables - Adjust as needed
PYTHON = poetry run python
POETRY = poetry
PYTEST = poetry run pytest
RUFF = poetry run ruff
MYPY = poetry run mypy
ALEMBIC = poetry run alembic
PROTOC = $(PYTHON) -m grpc_tools.protoc
UVICORN = poetry run uvicorn
APP_MODULE ?= presentation.main:app
# Use project directory name as default Docker image name (lowercase)
DOCKER_IMAGE_NAME ?= $(shell basename $(CURDIR) | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9_.-]/-/g') # Sanitize name
DOCKER_TAG ?= latest
DOCKER_CONTAINER_NAME = $(DOCKER_IMAGE_NAME)-container
# Proto source and output directories
PROTO_SRC_DIR = infrastructure/grpc
PROTO_OUT_DIR = . # Output relative to project root

# Default target
default: help

help: ## Display this help message
	@echo "Available make commands for my_fastapi_project:"
	@echo ""
	@# Use awk to format help messages from comments starting with ##
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies from lock file (may not install project itself)
	@echo "--> Installing dependencies using Poetry..."
	$(POETRY) install --no-root

sync: ## Ensure virtual environment exactly matches lock file (recommended!)
	@echo "--> Syncing environment with lock file..."
	$(POETRY) sync --no-root

run: sync ## Run dev server (FastAPI + Uvicorn + Auto-reload)
	@echo "--> Running development server (http://localhost:8000)..."
	$(UVICORN) $(APP_MODULE) --host 0.0.0.0 --port 8000 --reload

run-prod: sync ## Run production-like server (Uvicorn workers or Gunicorn)
	@echo "--> Running production-like server (http://localhost:8000)..."
	# Option 1: Uvicorn with workers
	$(UVICORN) $(APP_MODULE) --host 0.0.0.0 --port 8000 --workers 4
	# Option 2: Gunicorn (add 'gunicorn' to deps)
	# poetry run gunicorn --bind 0.0.0.0:8000 --workers 4 --worker-class uvicorn.workers.UvicornWorker $(APP_MODULE)

test: ## Run tests using pytest
	@echo "--> Running tests..."
	$(PYTEST) -v tests/

test-cov: ## Run tests with coverage report (HTML + terminal)
	@echo "--> Running tests with coverage..."
	$(PYTEST) --cov=. --cov-branch --cov-report=term-missing --cov-report=html -v tests/
	@echo "Coverage report saved to htmlcov/index.html"

lint: ## Check code style with Ruff
	@echo "--> Checking code style with Ruff..."
	$(RUFF) check .

format: ## Format code with Ruff (fix fixable issues)
	@echo "--> Formatting code with Ruff..."
	$(RUFF) format .
	@echo "--> Applying automatic fixes with Ruff..."
	$(RUFF) check . --fix --show-fixes
	@echo "--> Re-checking style after formatting..."
	$(RUFF) check .

check: ## Run static type checking with MyPy
	@echo "--> Running static type checking with MyPy..."
	$(MYPY) .

check-all: format lint check test ## Run format, lint, type check, and tests

makemigrations: ## Generate new Alembic migration (Usage: make makemigrations m="Message")
	@echo "--> Generating new Alembic migration..."
	@[ -z "$(m)" ] && { echo "Usage: make makemigrations m=\"Your migration message\""; exit 1; } || :
	$(ALEMBIC) revision --autogenerate -m "$(m)"

migrate: ## Apply database migrations using Alembic (to 'head')
	@echo "--> Applying Alembic migrations..."
	$(ALEMBIC) upgrade head

migrate-down: ## Revert last migration (Usage: make migrate-down [rev=-1])
	@echo "--> Reverting Alembic migration (steps: ${rev=-1})..."
	$(ALEMBIC) downgrade ${rev}

generate-grpc: ## Generate Python gRPC code from .proto files
	@echo "--> Generating gRPC code from proto files in $(PROTO_SRC_DIR)..."
	@if compgen -G "$(PROTO_SRC_DIR)/*.proto" > /dev/null; then \
		$(PROTOC) \
			-I=$(PROTO_SRC_DIR) \
			--python_out=$(PROTO_OUT_DIR) \
			--pyi_out=$(PROTO_OUT_DIR) \
			--grpc_python_out=$(PROTO_OUT_DIR) \
			$(PROTO_SRC_DIR)/*.proto; \
		echo "gRPC code generated."; \
	else \
		echo "No *.proto files found in $(PROTO_SRC_DIR). Skipping generation."; \
	fi

clean: ## Remove cache files, build artifacts, and coverage reports
	@echo "--> Cleaning up cache files and build artifacts..."
	find . -type f \( -name "*.py[co]" -o -name "*~" -o -name "*.bak" \) -delete
	find . -type d \( -name "__pycache__" -o -name ".pytest_cache" -o -name ".mypy_cache" -o -name ".ruff_cache" -o -name "*.egg-info" \) -exec rm -rf {} +
	rm -rf htmlcov build dist .coverage* *.prof *.lprof

build: clean ## Build project distribution artifacts (wheel, sdist)
	@echo "--> Building project distribution..."
	$(POETRY) build

# --- Docker Commands ---
docker-build: ## Build the Docker image for the project
	@echo "--> Building Docker image $(DOCKER_IMAGE_NAME):$(DOCKER_TAG)..."
	docker build --build-arg PYTHON_VERSION=3.9 -t $(DOCKER_IMAGE_NAME):$(DOCKER_TAG) .

docker-run: ## Run application in a detached Docker container (uses .env)
	@echo "--> Running Docker container $(DOCKER_CONTAINER_NAME)..."
	@echo "NOTE: Ensure dependent services (DB, Redis) are running and accessible."
	docker run --rm -d --name $(DOCKER_CONTAINER_NAME) -p 8000:8000 --env-file .env $(DOCKER_IMAGE_NAME):$(DOCKER_TAG)
	@echo "Container started. Use 'make docker-logs' / 'make docker-stop'."

docker-stop: ## Stop the running Docker container
	@echo "--> Stopping Docker container $(DOCKER_CONTAINER_NAME)..."
	docker stop $(DOCKER_CONTAINER_NAME) || echo "Container not running or already stopped."

docker-logs: ## Follow logs from the running Docker container (Ctrl+C to stop)
	@echo "--> Following logs for container $(DOCKER_CONTAINER_NAME)..."
	@docker logs -f $(DOCKER_CONTAINER_NAME) || echo "Container not found."

# --- Docker Compose Commands (Example - Uncomment if using docker-compose) ---
# DOCKER_COMPOSE = docker-compose

# docker-compose-up: ## Start services defined in docker-compose.yml (detached)
#	@echo "--> Starting services with Docker Compose..."
#	$(DOCKER_COMPOSE) up -d --remove-orphans

# docker-compose-down: ## Stop and remove services defined in docker-compose.yml
#	@echo "--> Stopping services with Docker Compose..."
#	$(DOCKER_COMPOSE) down --remove-orphans -v # -v removes volumes

