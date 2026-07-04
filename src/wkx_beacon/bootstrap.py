"""Assemble the app: settings, plugin discovery, config resolution."""

import logging
from dataclasses import dataclass

from wkx_beacon.config import ResolvedReport, Settings, load_config, resolve
from wkx_beacon.plugin import PluginRegistry, discover
from wkx_beacon.store import Store

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    settings: Settings
    store: Store
    reports: list[ResolvedReport]


def bootstrap(
    settings: Settings | None = None, registry: PluginRegistry | None = None
) -> AppContext:
    """Fail here, at boot, not at 07:00."""
    settings = settings or Settings()  # type: ignore
    registry = registry or discover()
    config = load_config(settings.config_file)
    reports = resolve(config, registry)
    logger.info("bootstrapped %d report(s)", len(reports))
    return AppContext(settings=settings, store=Store(settings.data_dir), reports=reports)
