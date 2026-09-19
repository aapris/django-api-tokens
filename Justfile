# django-api-tokens — task runner. Run `just` to list the recipes.
#
# Shared conventions across our projects (see the "Task Runner (Justfile)" section of the
# global development guidelines in ~/.claude/CLAUDE.md). This is a library: there is no
# `dev` (nothing to start), no docker group, and no `check` (no type checker), so `ci`
# is `lint test`.

set positional-arguments := true

lint_paths := "src tests"

[private]
default:
    @just --list --unsorted

# --- setup -------------------------------------------------------------------

# Install/sync the Python virtual environment.
[group('setup')]
install:
    uv sync

[doc('One-time developer setup: dependencies + git hooks.')]
[group('setup')]
setup: install
    uvx prek install

[doc('Run all git hooks against all files.')]
[group('setup')]
hooks:
    uvx prek run --all-files

# --- quality -----------------------------------------------------------------

# Run the test suite.
[group('quality')]
test *args:
    uv run pytest "$@"

# What is measured lives in pyproject.toml under [tool.coverage.run].
[doc('Run the test suite with a coverage report.')]
[group('quality')]
cov *args:
    uv run pytest --cov --cov-report=term-missing "$@"

[doc('Lint and format-check (no changes written).')]
[group('quality')]
lint:
    uv run ruff check {{ lint_paths }}
    uv run ruff format --check {{ lint_paths }}

# Auto-fix lint issues and format the code.
[group('quality')]
fmt:
    uv run ruff check --fix {{ lint_paths }}
    uv run ruff format {{ lint_paths }}

# The local pre-push gate.
[group('quality')]
ci: lint test

# --- project -----------------------------------------------------------------

# Generate a migration after a model change, e.g. `just makemigrations -n add_note_field`.
[doc('Generate api_tokens migrations against the test settings.')]
[group('project')]
makemigrations *args:
    uv run django-admin makemigrations api_tokens --settings tests.settings --pythonpath . "$@"
