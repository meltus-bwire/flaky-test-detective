.PHONY: demo test lint check

demo:
	@echo "Demo is not available until M1-006."

test:
	uv run pytest -q

lint:
	uv run ruff check .
	uv run ruff format --check .

check:
	uv run ty check src/
