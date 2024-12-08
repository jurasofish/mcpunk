
test:
	uv run --frozen pytest ./tests --verbose --color=yes

test-coverage:
	uv run --frozen pytest ./tests  --cov . --cov-branch --cov-report html --cov-config=.coveragerc --verbose --color=yes

ruff-lint-fix:
	uv run --frozen ruff check . --fix
ruff-lint-check:
	uv run --frozen ruff check .

ruff-format-fix:
	uv run --frozen ruff format .
ruff-format-check:
	uv run --frozen ruff format . --check

mypy-check:
	uv run --frozen mypy ./mcpunk
	uv run --frozen mypy ./tests

pre-commit-check:
	uv run --frozen pre-commit run --all-files

lint-check: ruff-lint-check ruff-format-check mypy-check pre-commit-check
lint-fix: ruff-format-fix ruff-lint-fix ruff-format-fix mypy-check pre-commit-check

# Intended to be used before committing to auto-fix what can be fixed and check the rest.
lint: lint-fix

install-dev:
	uv sync --extra dev
	uv pip install -e .
