.PHONY: init down down-clear docker-up docker-down docker-down-clear docker-pull docker-build-pull run lint format install

init: docker-down docker-pull docker-build-pull docker-up

down: docker-down

down-clear: docker-down-clear

docker-up:
	docker compose up -d

docker-down:
	docker compose down --remove-orphans

docker-down-clear:
	docker compose down -v --remove-orphans

docker-pull:
	docker compose pull

docker-build-pull:
	docker compose build --pull

install:
	pip install -e ".[dev]"

run:
	python -m app

lint:
	ruff check app/
	mypy app/

format:
	ruff check --fix app/
	ruff format app/
