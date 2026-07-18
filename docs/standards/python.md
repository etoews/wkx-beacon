# Python standards

The Python development standard for wkx-beacon. Distilled from the canonical, machine-wide
conventions at [github.com/etoews/python](https://github.com/etoews/python)
([`PROJECT.md`](https://github.com/etoews/python/blob/main/PROJECT.md) is the per-project layer;
[`MAC.md`](https://github.com/etoews/python/blob/main/MAC.md) is the one-time machine setup). This
file keeps only what is relevant to this repo, with beacon's own names in the examples. When it and
the canonical source disagree, the canonical source wins; open an issue rather than diverging
silently.

wkx-beacon is an application (not a library), so the app-only rules below (CLI, config built at the
entry point, logging configured once) apply in full.

## Stack

| Purpose | Tool |
|---|---|
| Deps and envs | **uv** |
| Lint and format | **ruff** |
| Tests | **pytest** (plus `pytest-cov`) |
| Type check | **ty** (fall back to mypy per project if ty blocks a legitimate pattern) |
| Logging | stdlib `logging` |
| CLI | **Typer** |
| Config | **pydantic-settings** |

Python 3.14, `src/` layout, `pyproject.toml` as the single source of truth, `uv.lock` committed.

## The commit gate

These four run clean before every commit, and CI is the enforcer (`.github/workflows/ci.yml`):

```bash
uv run ruff check          # lint (--fix locally; no --fix in CI)
uv run ruff format --check  # format (drop --check locally to apply)
uv run ty check            # type check
uv run pytest              # tests
```

`.pre-commit-config.yaml` runs ruff and ty as a fast local gate, but it can be skipped, so CI stays
the source of truth. Keep the `ruff-pre-commit` rev in sync with the `ruff` dev dependency.

## Project layout

`src/` layout, so tests import the installed package and packaging mistakes surface early.

```
src/wkx_beacon/         # the one package; nothing importable lives outside src/
tests/                  # not a package: no __init__.py; pytest discovers by path
```

- Mirror the package structure under `tests/`.
- Commit `pyproject.toml`, `uv.lock`, `.python-version`. Gitignore `.venv/`, caches, `.env`, `data/`.

## pyproject.toml

Single source of truth for metadata, build, dependencies, and tool config. Dev deps live in
`[dependency-groups]` (`uv add --dev` writes there). Pin **lower bounds only** in `[project]`
(`fastapi>=0.115`); `uv.lock` owns the upper bound. Pin exactly only for a known incompatibility,
with a one-line comment saying why (this repo pins `apscheduler>=3.10,<4` because 4.x is a different
API).

## Ruff

One tool for lint and format. Rule selection and per-file ignores this repo uses:

```toml
[tool.ruff]
line-length = 100
target-version = "py314"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "D"]   # tests use bare asserts and need no docstrings

[tool.ruff.format]
quote-style = "double"
```

## Pytest

Config lives in `[tool.pytest.ini_options]`:

```toml
testpaths = ["tests"]
addopts = "-ra --strict-markers --strict-config"
filterwarnings = ["error"]   # warnings are failures in tests
```

- Name `test_*.py`, `Test*`, `test_*`. Fixtures go in `conftest.py` at the nearest common ancestor.
- **Parametrize, do not loop** (`@pytest.mark.parametrize`), so the first failure does not hide the
  rest.
- Structure each test **Arrange-Act-Assert**, separated by blank lines. More than one Act means
  split the test.
- Coverage: `uv run pytest --cov=wkx_beacon --cov-report=term-missing`. No coverage gating in CI
  while the suite matures.

## Type checking

**Everything is typed**, in `src/` and `tests/`. Every function and method has a full signature
including `-> None`; class attributes are annotated, not just `__init__` parameters; tests count
(`def test_foo() -> None:`). `ty check` is part of the commit gate.

Modern syntax only: `list[int]`, `dict[str, X]`, `X | None`. No `typing.List` / `Optional` / `Union`
imports. Never a bare `# type: ignore`; always name the rule (`# type: ignore[arg-type]`).

## Docstrings

Google style. Document **intent, not mechanics**: preconditions the caller must meet, what "empty"
or "missing" means, exceptions raised and when, non-obvious side effects. A docstring that restates
an obvious signature is noise. One-line docstrings are fine for obvious functions.

## Logging

stdlib `logging`, never `print()` in library or application code (a CLI writing to stdout is a
separate channel; keep diagnostics on `logging` to stderr).

- Module-level logger: `logger = logging.getLogger(__name__)`. Never the root logger.
- The package adds a `NullHandler` in `src/wkx_beacon/__init__.py`; the **application configures
  logging once** at the entry point (`wkx_beacon._logging.configure()`), driven by `LOG_LEVEL` and
  `LOG_FORMAT` (`json` in the container image, human-readable otherwise).
- **`%` formatting for lazy eval**: `logger.debug("fetched %s items", len(items))`, not an f-string.
- `logger.exception(...)` inside `except`.
- **Never log** secrets, tokens, PII, or report contents. Log identifiers (`report_name`, `run_id`),
  not payloads.

## CLI

Typer, because it turns the type hints you already write into args, options, help, and validation.
Pair with `rich` for styled stdout if needed; keep `logging` for diagnostics on stderr. Prefer
`typer.echo` over `print`. The console-script entry point is declared in `pyproject.toml`
(`beacon = "wkx_beacon.__main__:main"`). Configure logging in an `@app.callback()` before any
subcommand runs.

## Error handling

**Raise specific exceptions from a project hierarchy** (`src/wkx_beacon/exceptions.py`): `BeaconError`
is the base, with `ConfigError`, `CollectError`, `RenderError`, `StoreError`, `NotifyError` under it.
Callers catch `BeaconError` for "anything from beacon" or a subclass for targeted handling.

**Translate third-party exceptions at the boundary** where your code meets the external library, and
preserve the chain with `from e`:

```python
except botocore.exceptions.ClientError as e:
    raise CollectError(f"cost explorer call failed: {e}") from e
```

`except ... pass` is a bug unless a one-line comment says why it is safe. Never a bare `except:`; use
`except Exception:` at minimum so `KeyboardInterrupt` still kills the process.

## Configuration and secrets

**One typed config object, built once at the entry point, passed down explicitly.** Nothing deep in
the call stack reads `os.environ`; if a function needs a value, it takes it as a parameter.

Use `pydantic-settings`. Beacon's `Settings` uses `env_prefix="BEACON_"`, reads `.env`, and sets
`extra="forbid"` so a typo'd `BEACON_*` variable is a startup error, not a silent no-op. Required
fields have no default, so missing config fails at boot, not at first use. Use `SecretStr` for every
secret so it is masked in logs and reprs; call `.get_secret_value()` only at the point of use.

- `.env` is never committed (it is gitignored). Commit `.env.example` as the documented contract.
- In production, secrets come from the host platform's secret store (SSM under `/wkx/beacon/<env>/`),
  not a `.env` file.

## Dependency management

```bash
uv add <pkg>            # runtime dep
uv add --dev <pkg>      # dev dep
uv remove <pkg>
uv lock --upgrade-package <pkg>   # bump one
uv lock --upgrade                 # bump all
uv sync                           # apply to .venv (uv sync --locked in CI)
```

Never bare `pip install` (it fails anyway under `PIP_REQUIRE_VIRTUALENV=1`). Commit a `uv.lock` bump
in a single-purpose commit (`deps: upgrade boto3 to 1.36`). Use `uv tool install` for global CLI
tools (ruff, pre-commit), not project deps.

## Upgrading Python

One project at a time, one commit. Pin with `uv python pin 3.X`; set `requires-python = ">=3.X"` and
ruff `target-version = "py3X"`; `rm -rf .venv && uv sync`; modernise syntax with
`uv run ruff check --select UP --fix`; run the full commit gate; commit as `python: upgrade to 3.X`
in isolation. Full steps in the canonical
[`PROJECT.md` §13](https://github.com/etoews/python/blob/main/PROJECT.md).

## Reference

Full templates (`pyproject.toml`, CI workflow, `_logging.py`, Typer entry point, pre-commit config)
and the complete command reference live in the canonical source at
[github.com/etoews/python](https://github.com/etoews/python). This repo already embodies them; use
them when adding a new module or plugin, and match the surrounding code.
