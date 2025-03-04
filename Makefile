.PHONY: clean install format lint test security build all

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -f .coverage
	find . -type d -name '__pycache__' -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete

install:
	poetry install --with dev

format:
	poetry run black .
	poetry run isort --profile black .
	poetry run ruff check --fix .

lint:
	poetry run black --check .
	poetry run isort --check-only --profile black .
	poetry run ruff check .

test:
	poetry run pytest

security:
	poetry run bandit -r src/

build: clean test
	poetry build

all: clean install format lint test security build
