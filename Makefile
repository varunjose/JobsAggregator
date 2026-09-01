.PHONY: install dev test lint sync docker-up

install:
	python -m pip install -e ".[dev]"

dev:
	uvicorn app.main:app --reload

test:
	pytest

lint:
	ruff check .

sync:
	python -m app.cli sync

docker-up:
	docker compose up --build
