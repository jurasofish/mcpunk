
test: install
	uv run --frozen --all-extras --all-groups pytest ./tests --verbose --color=yes --durations=10

test-coverage: install
	uv run --frozen --all-extras --all-groups pytest ./tests  --cov . --cov-branch --cov-report html --cov-config=.coveragerc --verbose --color=yes --durations=10

ruff-lint-fix: install
	uv run --frozen --all-extras --all-groups ruff check . --fix
ruff-lint-check: install
	uv run --frozen --all-extras --all-groups ruff check .

ruff-format-fix: install
	uv run --frozen --all-extras --all-groups ruff format .
ruff-format-check: install
	uv run --frozen --all-extras --all-groups ruff format . --check

mypy-check: install
	uv run --frozen --all-extras --all-groups mypy ./mcpunk
	uv run --frozen --all-extras --all-groups mypy ./tests

pre-commit-check: install
	uv run --frozen --all-extras --all-groups pre-commit run --all-files

lint-check: ruff-lint-check ruff-format-check mypy-check pre-commit-check
lint-fix: ruff-format-fix ruff-lint-fix ruff-format-fix mypy-check pre-commit-check

# Intended to be used before committing to auto-fix what can be fixed and check the rest.
lint: lint-fix

install:
	uv sync --all-extras --all-groups --frozen
	uv pip install -e .
