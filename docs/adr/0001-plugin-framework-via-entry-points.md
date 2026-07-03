# Plugin framework via entry points from day one

Beacon's value is the matrix of report types, platforms, formats, and channels, so the plugin API is the product: collectors, renderers, and notifiers are discovered through the entry-point groups `wkx_beacon.collectors`, `wkx_beacon.renderers`, and `wkx_beacon.notifiers`, behind a semver-governed public surface (`wkx_beacon.plugin`). We chose this over the YAGNI path (typed Protocol seams in-repo, framework later) because retrofitting a public plugin API after third parties depend on internals is far costlier than carrying one from the start; the built-in plugins register through the same entry points so the third-party path is exercised continuously.

## Considered options

- Typed seams only, one implementation each, framework later (rejected: the OSS pitch is the plugin matrix, and a later API break would strand early adopters)
- Full framework now (chosen)
