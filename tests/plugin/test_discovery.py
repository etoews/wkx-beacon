from collections.abc import Iterable
from types import SimpleNamespace
from typing import Any

import pytest
from fakes import FakeCollector, FakeNotifier, FakeRenderer

from wkx_beacon.exceptions import ConfigError
from wkx_beacon.plugin.discovery import (
    GROUP_COLLECTORS,
    GROUP_NOTIFIERS,
    GROUP_RENDERERS,
    discover,
)


def _entry_points_fn(group: str) -> Iterable[Any]:
    table = {
        GROUP_COLLECTORS: [SimpleNamespace(name="fake-collector", load=lambda: FakeCollector)],
        GROUP_RENDERERS: [SimpleNamespace(name="fake-renderer", load=lambda: FakeRenderer)],
        GROUP_NOTIFIERS: [SimpleNamespace(name="fake-notifier", load=lambda: FakeNotifier)],
    }
    return table[group]


def test_discover_builds_registry_from_entry_points() -> None:
    registry = discover(_entry_points_fn)

    assert registry.collectors == {"fake-collector": FakeCollector}
    assert registry.renderers == {"fake-renderer": FakeRenderer}
    assert registry.notifiers == {"fake-notifier": FakeNotifier}


def test_duplicate_plugin_name_is_a_boot_error() -> None:
    def duplicated(group: str) -> Iterable[Any]:
        if group == GROUP_COLLECTORS:
            return [
                SimpleNamespace(name="fake-collector", load=lambda: FakeCollector),
                SimpleNamespace(name="fake-collector", load=lambda: FakeCollector),
            ]
        return []

    with pytest.raises(ConfigError, match="duplicate"):
        discover(duplicated)
