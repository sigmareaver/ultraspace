# ULTRASPACE developer entry points. Commands documented in AGENTS.md.
# Always via uv — never bare python/pip (docs/engineering/tech-stack.md).

.PHONY: setup check test lint format types selftest binder clean

setup:
	uv sync

## Fast gate — keep green ALWAYS (docs/process/workflow.md)
check: lint types
	uv run pytest -m "not slow"

## Full suite (grows conformance/determinism/perf stages by milestone)
test: lint types
	uv run pytest

lint:
	uv run ruff check src tests tools
	uv run ruff format --check src tests tools
	uv run python tools/check_imports.py
	uv run python tools/check_units.py

format:
	uv run ruff format src tests tools
	uv run ruff check --fix src tests tools

types:
	uv run mypy

selftest:
	uv run python -m ultraspace selftest

## Regenerate committed manual tables (data/manuals/*/generated/)
generate:
	uv run python -m ultraspace generate

generate-check:
	uv run python -m ultraspace generate --check

## Export the printable manual binder (HTML) to build/binder/site/
binder:
	uv run python tools/export_binder.py

clean:
	rm -rf .venv .pytest_cache .mypy_cache .ruff_cache .hypothesis dist build
	find . -type d -name __pycache__ -exec rm -rf {} +
