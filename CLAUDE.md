# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository.

## What this is

wkx-beacon is an open-source, containerised Python web app that generates reports about the platform
it runs on and announces them. It is built around a plugin framework with three seams (collectors
gather data, renderers turn it into artefacts, notifiers announce runs), a cron scheduler, and a
read-only htmx viewer over a filesystem store. One container, one process.

Start here:

- [`README.md`](README.md) - what beacon is, the MVP slice, quickstart, configuration, plugin
  authoring, deployment.
- [`CONTEXT.md`](CONTEXT.md) - the canonical ubiquitous language. Use these terms exactly.
- [`ROADMAP.md`](ROADMAP.md) - build order, deliverables, and status.
- [`docs/superpowers/specs/2026-07-04-wkx-beacon-design.md`](docs/superpowers/specs/2026-07-04-wkx-beacon-design.md)
  - the full architecture and design rationale.
- [`docs/adr/`](docs/adr) - the decisions and why they were made.

## Python conventions

**For anything Python related - project layout, `pyproject.toml`, uv, ruff, pytest, ty, logging,
docstrings, error handling, config and secrets, dependency management, the Typer CLI - follow
[`docs/standards/python.md`](docs/standards/python.md).** That is the repo's distilled Python
standard and the routing target: read it before writing or reviewing Python here. It is distilled
from the canonical source at [github.com/etoews/python](https://github.com/etoews/python); reference
that URL, not a local path, for the original.

The two rules worth stating up front (the standard has the rest):

- All Python work uses **uv**. Never bare `pip install`.
- Everything is typed, and `ruff check`, `ruff format --check`, `ty check`, and `pytest` all pass
  before every commit.

## Domain and code invariants

- **The ubiquitous language in `CONTEXT.md` is canonical.** Use its terms exactly. In particular,
  the concept is spelled "artefact" in prose but `artifacts/` in code paths and URLs.
- **ADR-0002**: no authentication or authorisation anywhere in beacon; that belongs to the host
  platform. Do not add login screens, sessions, or API keys.
- **ADR-0003**: no database. The filesystem store is the only state.
- **Money is `Decimal`, never `float`.** Billing data is always UTC calendar days and UTC months;
  local dates are display labels only.
- Raise `BeaconError` subclasses; translate third-party exceptions at the boundary with
  `raise X(...) from e`.
- The plugin API (`wkx_beacon.plugin`) is a semver-governed product surface. Breaking it breaks third
  parties; see [ADR-0001](docs/adr/0001-plugin-framework-via-entry-points.md).

## Conventions

New Zealand English, no em dashes, in all prose (docstrings, README, docs). Diagrams in Mermaid.
Global git and writing conventions in `~/.claude/CLAUDE.md` apply: branch `feat/<slug>` before
touching code, never author on `main`, no merge commits.
