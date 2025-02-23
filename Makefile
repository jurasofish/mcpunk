
test:
	uv run --frozen --all-extras --all-groups pytest ./tests --verbose --color=yes --durations=10

test-coverage:
	uv run --frozen --all-extras --all-groups pytest ./tests  --cov . --cov-branch --cov-report html --cov-config=.coveragerc --verbose --color=yes --durations=10

ruff-lint-fix:
	uv run --frozen --all-extras --all-groups ruff check . --fix
ruff-lint-check:
	uv run --frozen --all-extras --all-groups ruff check .

ruff-format-fix:
	uv run --frozen --all-extras --all-groups ruff format .
ruff-format-check:
	uv run --frozen --all-extras --all-groups ruff format . --check

mypy-check:
	uv run --frozen --all-extras --all-groups mypy ./mcpunk
	uv run --frozen --all-extras --all-groups mypy ./tests

pre-commit-check:
	uv run --frozen --all-extras --all-groups pre-commit run --all-files

lint-check: ruff-lint-check ruff-format-check mypy-check pre-commit-check
lint-fix: ruff-format-fix ruff-lint-fix ruff-format-fix mypy-check pre-commit-check

# Intended to be used before committing to auto-fix what can be fixed and check the rest.
lint: lint-fix

install:
	uv sync --all-extras --all-groups --frozen
	uv pip install -e .
