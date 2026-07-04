"""Public plugin API surface. Import from here, not from submodules."""

from wkx_beacon.plugin.contracts import (
    Artefact,
    Collector,
    Notifier,
    Renderer,
    ReportData,
    RunStatus,
    RunSummary,
)
from wkx_beacon.plugin.discovery import (
    GROUP_COLLECTORS,
    GROUP_NOTIFIERS,
    GROUP_RENDERERS,
    PluginRegistry,
    discover,
)

__all__ = [
    "GROUP_COLLECTORS",
    "GROUP_NOTIFIERS",
    "GROUP_RENDERERS",
    "Artefact",
    "Collector",
    "Notifier",
    "PluginRegistry",
    "Renderer",
    "ReportData",
    "RunStatus",
    "RunSummary",
    "discover",
]
