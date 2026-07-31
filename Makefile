.PHONY: help install dev test lint format migrate run docker-up docker-down clean

help: ## نمایش این راهنما
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## نصب وابستگی‌ها
	poetry install

dev: install ## نصب و راه‌اندازی محیط توسعه
	cp -n .env.example .env
	poetry run alembic upgrade head

run: ## اجرای ربات
	poetry run python -m anonchat.main

test: ## اجرای تست‌ها
	poetry run pytest -v

lint: ## بررسی کیفیت کد
	poetry run ruff check src/ tests/
	poetry run ruff format --check src/ tests/

format: ## فرمت‌بندی کد
	poetry run ruff check --fix src/ tests/
	poetry run ruff format src/ tests/

migrate: ## اجرای مهاجرت‌ها
	poetry run alembic upgrade head

migrate-new: ## ساخت مهاجرت جدید (NAME=...)
	poetry run alembic revision --autogenerate -m "$(NAME)"

docker-up: ## اجرا با Docker
	docker-compose up -d

docker-down: ## توقف Docker
	docker-compose down

docker-logs: ## مشاهده‌ی لاگ Docker
	docker-compose logs -f

clean: ## پاک‌سازی فایل‌های موقت
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	rm -rf .coverage htmlcov cov_html
	rm -f *.db test.db
