.PHONY: build up down logs test lint migrate migration shell

build:
	docker compose build

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f api

test:
	docker compose run --rm api pytest -q

lint:
	docker compose run --rm api ruff check app tests

migrate:
	docker compose run --rm api alembic upgrade head

migration:
	docker compose run --rm api alembic revision --autogenerate -m "$(m)"

shell:
	docker compose exec api /bin/bash
