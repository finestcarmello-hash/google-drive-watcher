# Chaturbate Online Watcher Makefile

.PHONY: help install test run clean docker-build docker-run docker-stop

# Default target
help:
	@echo "Available targets:"
	@echo "  install      - Install dependencies"
	@echo "  test         - Run tests"
	@echo "  run          - Run the watcher"
	@echo "  clean        - Clean up generated files"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run   - Run in Docker container"
	@echo "  docker-stop  - Stop Docker container"

# Install dependencies
install:
	pip install -r requirements.txt

# Run tests
test:
	python -m pytest tests/ -v

# Run the watcher
run:
	python -m src.main

# Clean up generated files
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .pytest_cache/
	rm -rf logs/
	rm -f .status.json

# Docker targets
docker-build:
	docker build -t cb-online-watcher .

docker-run:
	docker run -d \
		--name cb-watcher \
		--env-file .env \
		-v $(PWD)/logs:/app/logs \
		-v $(PWD)/.status.json:/app/.status.json \
		cb-online-watcher

docker-stop:
	docker stop cb-watcher
	docker rm cb-watcher

# Development targets
dev-install:
	pip install -r requirements.txt
	pip install -e .

# Format code (if you add black/flake8 later)
format:
	@echo "No formatter configured yet"

# Lint code (if you add flake8 later)
lint:
	@echo "No linter configured yet"