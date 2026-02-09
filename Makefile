.PHONY: setup test test-one lint typecheck check clean install uninstall uninstall-purge

# Development setup
setup:
	uv sync --dev

# Run all tests with coverage
test:
	uv run pytest --cov=instincts --cov-report=term-missing

# Run specific test(s)
# Usage:
#   make test-one T=tests/test_models.py
#   make test-one T=tests/test_models.py::TestPattern
#   make test-one T=tests/test_models.py::TestPattern::test_pattern_is_frozen
#   make test-one T="-k confidence"
test-one:
	uv run pytest $(T) -v

lint:
	uv run ruff check instincts scripts tests

typecheck:
	uv run mypy instincts scripts

check: typecheck test  ## Run all checks before PR

clean:
	rm -rf .pytest_cache .mypy_cache .coverage htmlcov .venv uv.lock
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Install/Uninstall to ~/.claude/
install:
	uv run python -m scripts.install

uninstall:
	uv run python -m scripts.uninstall

uninstall-purge:
	uv run python -m scripts.uninstall --purge
