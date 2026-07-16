.PHONY: demo test lint check

demo:
	uv run detective run --fixture shared
	uv run detective run --fixture race
	uv run detective run --fixture time

test:
	uv run pytest -q

lint:
	uv run ruff check .
	uv run ruff format --check .

check:
	uv run ty check src/
