.PHONY: help install install-dev test lint format type-check docs docs-serve clean build

help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

install: ## Install package in production mode
	pip install -e .

install-dev: ## Install package with development dependencies
	pip install -e ".[dev]"

test: ## Run tests
	pytest

test-cov: ## Run tests with coverage
	pytest --cov=apibackuper --cov-report=html --cov-report=term

lint: ## Run linters
	flake8 apibackuper --max-line-length=100 --extend-ignore=E203
	bandit -r apibackuper -ll

format: ## Format code with black and isort
	black --line-length=100 apibackuper tests
	isort --profile=black --line-length=100 apibackuper tests

format-check: ## Check code formatting without making changes
	black --check --line-length=100 apibackuper tests
	isort --check-only --profile=black --line-length=100 apibackuper tests

type-check: ## Run type checker
	mypy apibackuper --ignore-missing-imports --no-strict-optional

docs: ## Build documentation site (Docusaurus)
	cd docs && npm ci && npm run build

docs-serve: ## Serve documentation locally (Docusaurus)
	cd docs && npm start

clean: ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf htmlcov/
	rm -rf docs/build/
	rm -rf docs/.docusaurus/
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete

build: ## Build distribution packages
	python -m build

pre-commit-install: ## Install pre-commit hooks
	pre-commit install

pre-commit-run: ## Run pre-commit hooks on all files
	pre-commit run --all-files

check-all: format-check lint type-check test ## Run all checks

ci: check-all ## Run all CI checks (alias for check-all)
