# Authn and authz belong to the host platform, not beacon

Beacon implements no authentication or authorisation: reports are protected by whatever the platform beacon runs on provides at its edge (for the WKX Platform, a future decision such as Cloudflare Access; today, nothing, so the viewer is public). Do not add login screens, sessions, or API keys to beacon; the deliberate mitigations are that artefacts render no account identifiers and the viewer sets conservative security headers.

## Consequences

- The viewer is public until the WKX Platform makes its authn decision; spend patterns are visible to anyone with the URL, and this is accepted.
- A future contributor who finds "a web app with no auth" should read this ADR before fixing it.
