# wkx-beacon

Beacon generates reports about the platform it runs on and announces them. This glossary is the canonical ubiquitous language for beacon. Beacon is its own bounded context: where a term here differs from the WKX Platform glossary (`wkx-platform/CONTEXT.md`), beacon's meaning applies inside this repo, and the substrate is always named "WKX Platform" in full.

## Language

### Observing

**Platform**:
The kind of environment beacon runs on and reports on: `aws`, `azure`, `docker-compose`. A kind, not an instance. Distinct from the WKX Platform, which is one substrate instance that beacon (as an App) runs on; when both meanings could apply, say "WKX Platform" in full.
_Avoid_: source, provider, environment

**Report type**:
The kind of question a report answers: `cost`, `test`, `ai-eval`, `usage`, `error`. Open-ended; plugins can introduce new ones.

**Report**:
A named, configured wiring of one collector, one or more renderers, one or more notifiers, and a schedule.

**Report name**:
The unique slug (lowercase letters, digits, hyphens) that is a report's identity, its URL segment, and its store directory. Renaming creates a new identity; the old history is detached, not migrated.

**Run**:
One execution of a report, producing artefacts and a run record. A failed run is still a run.

**Published**:
The state of a run whose artefacts made it into the store, whatever happened afterwards. Only published runs are servable as a report's latest.

**Run status**:
`ok` (every stage clean), `degraded` (published, but a renderer or notifier failed), or `failed` (not published).
_Avoid_: success/failure as the only two states

**Artefact**:
A rendered output of a run, self-contained and immutable once written. Spelled `artifacts/` in code paths and URLs.
_Avoid_: output, file, page

### Plugins

**Collector**:
A plugin that gathers data from a platform and returns typed report data. Specific to one (report type, platform) pair; owns the data contract for its report type.

**Renderer**:
A plugin that turns report data into artefacts.

**Notifier**:
A plugin that announces a completed run on a channel. Sees the run summary, never raw platform data.

**Template pack**:
The templates a collector contributes so the `html` renderer can shape its report type.

### Cost reporting

**Billing day**:
A UTC calendar day, the bucket AWS bills in. The underlying day of every cost figure, whatever date label the display shows.
_Avoid_: local day (as a data concept; local dates are display labels only)

**Latest complete billing day**:
The most recent UTC day whose cost data is complete. What the "Yesterday" figure actually means.

### Storing and serving

**Store**:
The filesystem layout holding run records and artefacts. The only state beacon has.

**Run record**:
The metadata of one run: status, stage outcomes, timings, headline summary.
_Avoid_: run metadata, run manifest
