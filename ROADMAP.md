# wkx-beacon Roadmap

Build order, deliverables, and a hands-on artefact at every milestone.

For the full design rationale, see
[docs/superpowers/specs/2026-07-04-wkx-beacon-design.md](docs/superpowers/specs/2026-07-04-wkx-beacon-design.md).
For the canonical terms (report, run, artefact, published, store), see [CONTEXT.md](CONTEXT.md).

Beacon's value is the matrix of **report types** (cost, test, ai-eval, usage, error), **formats**
(html, json, markdown, ...), and **channels** (email, ms-teams, discord, ...) it can grow into. M0
is the one vertical slice through every seam; each later milestone widens one seam, contributed as a
plugin without touching core. Carry-forward notes live under the most recently completed milestone.

## Contents

| Milestone | Size | Status |
|-----------|------|--------|
| [M0: MVP vertical slice (cost report, html, email)](#m0-mvp-vertical-slice) | L | ✅ Complete |
| [M1: Test report](#m1-test-report) | M | ⬜ Next |
| [M2: AI eval report](#m2-ai-eval-report) | M | ⬜ Not started |
| [M3: Usage report](#m3-usage-report) | M | ⬜ Not started |
| [M4: Error report](#m4-error-report) | M | ⬜ Not started |
| [M5: Output formats (JSON, Markdown)](#m5-output-formats) | M | ⬜ Not started |
| [M6: Notification channels (SMTP, MS Teams, Discord)](#m6-notification-channels) | M | ⬜ Not started |
| [M7: Retention and operations](#m7-retention-and-operations) | M | ⬜ Not started |
| [M8: More platforms (Azure, Docker Compose)](#m8-more-platforms) | L | ⬜ Deferred |

**Sizes:** S = ≤ a session. M = a focused weekend or 2 evenings. L = several sessions, expect
debugging.

**Critical path:** M0 is the foundation and everything depends on it. After M0, the report-type
milestones (M1 to M4) are the core product sequence but are independently orderable. The format
milestone (M5) and the channel milestone (M6) are small, touch only their own seam, and can be
pulled forward whenever a report needs a new format or channel. M7 is cross-cutting. M8 is opt-in.

---

## M0: MVP vertical slice

The whole framework, proven end to end by one report: the WKX Platform member account's AWS spend
against its NZD $50/month budget, collected from Cost Explorer, rendered to a self-contained HTML
artefact, stored on the filesystem, served by the viewer, and emailed via Amazon SES daily at 07:00
Pacific/Auckland.

**Deliverables**
- [x] Project scaffold per [`docs/standards/python.md`](docs/standards/python.md): `src/` layout,
  Python 3.14, uv, ruff, pytest, ty, pre-commit, `BeaconError` hierarchy, logging setup.
- [x] Plugin framework: the three entry-point groups (`wkx_beacon.collectors`, `.renderers`,
  `.notifiers`), the semver-governed `wkx_beacon.plugin` API (typed `Collector`/`Renderer`/`Notifier`
  Protocols, `ReportData`/`Artefact`/`RunSummary`), entry-point discovery, and a reusable conformance
  test kit ([ADR-0001](docs/adr/0001-plugin-framework-via-entry-points.md)).
- [x] Configuration: `Settings` (env, `BEACON_` prefix, `extra="forbid"`) plus `beacon.toml` report
  wiring, with unknown plugin names, unknown config keys, and duplicate report names all boot errors.
- [x] Filesystem store ([ADR-0003](docs/adr/0003-filesystem-store-no-database.md)): run records and
  artefacts under `{data_dir}/reports/<name>/runs/<run-id>/`, `run.json` as the commit marker,
  latest-published lookup, path-traversal guards.
- [x] Report pipeline with the `ok` / `degraded` / `failed` status model: a failed run is still a run.
- [x] Cron scheduler (APScheduler, one job per report) with opt-in boot catch-up.
- [x] `aws-cost` collector (Cost Explorer, UTC billing days, `Decimal` money, USD / local-first
  display) and its cost template pack.
- [x] `html` renderer producing a self-contained artefact (autoescape forced on).
- [x] `email-ses` notifier (Amazon SES): headline plus a stable `/latest` link, never raw data.
- [x] Read-only FastAPI + Jinja2 + htmx viewer over the store, with `/healthz` and conservative
  security headers ([ADR-0002](docs/adr/0002-authn-belongs-to-the-host-platform.md): no authn in
  beacon).
- [x] Typer CLI: `beacon serve` (scheduler + viewer, the container entrypoint), `beacon run <report>`
  (one-shot), `beacon validate` (config and plugin discovery, no AWS credentials needed).
- [x] Container (arm64-first), `compose.yml`, `caddy.snippet`, GitHub Actions CI (ruff, ty, pytest,
  `beacon validate`, arm64 image build), README.

**Hands-on artefact**
- [x] `uv run beacon validate` passes from a fresh checkout.
- [x] `uv run beacon run platform-cost` (with AWS credentials) collects, renders, stores, and emails
  one cost report.
- [x] `uv run beacon serve` serves the report at `http://localhost:8000` and `/healthz` returns
  `{"status":"ok"}`.

### Carry-forward

- **Deferred by the design spec, now roadmap items:** other report types (M1 to M4), other formats
  (M5), other channels (M6), store retention (M7), and other platforms (M8).
- **Not tracked here:** the `wkx-platform` Terraform prerequisites (SES domain identity, IAM
  permissions for `ce:GetCostAndUsage` and `ses:SendEmail`, SSM parameters, log group, DNS, the
  deploy workflow) live in the `wkx-platform` repo, not this one. See the README deployment section.
- **On-demand generation** from the viewer stays out of scope: reports generate on schedule, plus the
  `beacon run` one-shot for development.

---

## M1: Test report

The first new report type, and the proof that adding a report type is a plugin, not a core change: a
new collector owning a new `ReportData` contract, plus a template pack the existing `html` renderer
shapes.

**Deliverables**
- [ ] A `test` report type with a collector (for example `github-actions-tests`, or a `junit`
  collector reading JUnit XML artefacts) returning a typed `TestReportData` (totals passed / failed /
  skipped, duration, slowest and newly-failing tests) and its `config_model`.
- [ ] A cost-style template pack for the `test` type so `html` can render it; headline is the
  pass/fail summary a notifier puts in a subject line.
- [ ] Plugin registration through the existing entry points, conformance-kit coverage, and unit tests
  with the collector's data source stubbed (no live calls in the suite).
- [ ] An example `[[report]]` block wiring the collector, `html`, and a notifier in `beacon.toml`, and
  a docs note on the new report type.

**Hands-on artefact**
- [ ] `uv run beacon run <test-report>` collects a test run, renders an HTML artefact, and announces
  it; the run shows in the viewer.

---

## M2: AI eval report

**Deliverables**
- [ ] An `ai-eval` report type with a collector returning a typed `AiEvalReportData` (per-suite
  scores, pass thresholds, regressions against the previous run, sample failures) and its
  `config_model`. Source is an evals harness output (result files or a harness API), stubbed in tests.
- [ ] A template pack for the `ai-eval` type, with a headline capturing overall score and any
  threshold breach.
- [ ] Conformance-kit coverage, unit tests, an example `beacon.toml` wiring, and docs.

**Hands-on artefact**
- [ ] `uv run beacon run <ai-eval-report>` produces an HTML eval report and announces a threshold
  breach or a clean pass.

---

## M3: Usage report

**Deliverables**
- [ ] A `usage` report type with a collector returning a typed `UsageReportData` (requests, active
  users or clients, top endpoints, per-service or per-env breakdown). Source is platform telemetry
  (for the WKX Platform, CloudWatch metrics or Caddy access logs), stubbed in tests.
- [ ] A template pack for the `usage` type; headline is the period's usage summary.
- [ ] Conformance-kit coverage, unit tests, an example `beacon.toml` wiring, and docs.

**Hands-on artefact**
- [ ] `uv run beacon run <usage-report>` produces an HTML usage report over a chosen window and
  announces it.

---

## M4: Error report

**Deliverables**
- [ ] An `error` report type with a collector returning a typed `ErrorReportData` (error rate, top
  error signatures, new-since-last-run errors, affected services). Source is log analytics (for the
  WKX Platform, CloudWatch Logs Insights over `/wkx/<service>/<env>`), stubbed in tests.
- [ ] A template pack for the `error` type; headline is the error-rate summary, so a notifier subject
  line reads at a glance.
- [ ] Conformance-kit coverage, unit tests, an example `beacon.toml` wiring, and docs.

**Hands-on artefact**
- [ ] `uv run beacon run <error-report>` produces an HTML error report and announces a spike or an
  all-clear.

---

## M5: Output formats

Widen the renderer seam so a report can be rendered to more than one format in a single run (a report
lists one or more renderers). Renderers are format-only and report-type-agnostic.

**Deliverables**
- [ ] A `json` renderer producing a machine-readable artefact of the report data (stable shape,
  suitable for downstream tooling).
- [ ] A `markdown` renderer producing a Markdown artefact (useful for embedding a summary in
  chat-channel notifications and in GitHub).
- [ ] Both registered through `wkx_beacon.renderers`, conformance-kit coverage, and viewer handling
  for serving non-HTML artefacts with the correct media type.
- [ ] Docs on multi-format reports (`renderers = ["html", "json", "markdown"]`).

**Hands-on artefact**
- [ ] A report configured with `html`, `json`, and `markdown` renderers produces all three artefacts
  in one run, all listed on the run's viewer page.

---

## M6: Notification channels

Widen the notifier seam beyond email. Notifiers see the run summary only, never raw platform data.

**Deliverables**
- [ ] An `smtp` notifier (generic SMTP, for deployments without SES).
- [ ] An `ms-teams` notifier (Microsoft Teams incoming webhook / Adaptive Card) carrying the headline
  and the `/latest` link.
- [ ] A `discord` notifier (Discord webhook embed) carrying the headline and the `/latest` link.
- [ ] All three registered through `wkx_beacon.notifiers`, each with a `config_model` (webhook URL as
  a `SecretStr`, never logged), conformance-kit coverage, and unit tests with the HTTP call stubbed.
- [ ] Docs on wiring multiple notifiers per report (`notifiers = ["email-ses", "ms-teams", "discord"]`).

**Hands-on artefact**
- [ ] A report with `ms-teams` and `discord` notifiers posts its headline and link to both channels on
  a run.

---

## M7: Retention and operations

Cross-cutting hardening once several report types are producing runs daily.

**Deliverables**
- [ ] Store retention: a configurable per-report policy that prunes old runs and their artefacts
  (keep last N and/or last D days), run on a schedule, with the latest published run always retained.
- [ ] Operational visibility: run outcomes surfaced as structured logs (already JSON in the container)
  and, where cheap, platform metrics for run status and duration.
- [ ] A runbook (`docs/runbooks/`) covering a failed scheduled run, a stuck scheduler, and restoring
  or resetting the data directory.
- [ ] Viewer polish for a multi-report, multi-format world: report index, per-report history, and
  clear `degraded` / `failed` indicators.

**Hands-on artefact**
- [ ] With retention configured, an old run is pruned on schedule while the latest published run stays
  servable.

---

## M8: More platforms

The collector contract is per (report type, platform) pair, so a second platform is new collectors,
not a core change. Deferred until a real second platform exists to report on.

**Deliverables**
- [ ] An `azure-cost` collector: the `cost` report type against Azure spend, reusing the cost template
  pack.
- [ ] A `compose-usage` collector: a `usage` report type against a Docker Compose platform (the WKX
  Platform on-prem home server), so beacon reports on the substrate it also runs on there.
- [ ] Docs on the (report type, platform) matrix and how a collector declares its `platform`.

**Hands-on artefact**
- [ ] A cost report configured with `azure-cost` renders and announces Azure spend through the same
  pipeline as `platform-cost`.
