"""Entry-point discovery. Built-ins and third-party plugins register the same way."""

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from typing import Any, Protocol

from wkx_beacon.exceptions import ConfigError

logger = logging.getLogger(__name__)

GROUP_COLLECTORS = "wkx_beacon.collectors"
GROUP_RENDERERS = "wkx_beacon.renderers"
GROUP_NOTIFIERS = "wkx_beacon.notifiers"


class EntryPointLike(Protocol):
    name: str

    def load(self) -> type: ...


EntryPointsFn = Callable[[str], Iterable[EntryPointLike]]


@dataclass
class PluginRegistry:
    collectors: dict[str, type] = field(default_factory=dict)
    renderers: dict[str, type] = field(default_factory=dict)
    notifiers: dict[str, type] = field(default_factory=dict)


def _default_entry_points(group: str) -> Iterable[Any]:
    return entry_points(group=group)


def _load_group(group: str, fn: EntryPointsFn) -> dict[str, type]:
    loaded: dict[str, type] = {}
    for ep in fn(group):
        if ep.name in loaded:
            raise ConfigError(f"duplicate plugin name {ep.name!r} in group {group!r}")
        loaded[ep.name] = ep.load()
        logger.debug("discovered plugin %s in %s", ep.name, group)
    return loaded


def discover(entry_points_fn: EntryPointsFn | None = None) -> PluginRegistry:
    """Discover all plugins. Injectable entry_points_fn keeps this testable."""
    fn = entry_points_fn or _default_entry_points
    return PluginRegistry(
        collectors=_load_group(GROUP_COLLECTORS, fn),
        renderers=_load_group(GROUP_RENDERERS, fn),
        notifiers=_load_group(GROUP_NOTIFIERS, fn),
    )
