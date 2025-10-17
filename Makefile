install:
	poetry install

lint:
	poetry run ruff check .
	poetry run black --check .
	poetry run isort --check .
	poetry run mypy .

test:
	poetry run pytest -q
