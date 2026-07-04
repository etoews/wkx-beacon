import pytest
from fakes import FakeCollector, FakeNotifier, FakeRenderer

from wkx_beacon.plugin import discover
from wkx_beacon.plugin.conformance import check_collector, check_notifier, check_renderer


def test_builtins_are_discoverable_via_real_entry_points() -> None:
    registry = discover()

    assert "aws-cost" in registry.collectors
    assert "html" in registry.renderers
    assert "email-ses" in registry.notifiers


def test_builtins_and_fakes_pass_conformance() -> None:
    registry = discover()
    for cls in (*registry.collectors.values(), FakeCollector):
        check_collector(cls)
    for cls in (*registry.renderers.values(), FakeRenderer):
        check_renderer(cls)
    for cls in (*registry.notifiers.values(), FakeNotifier):
        check_notifier(cls)


def test_conformance_rejects_a_broken_plugin() -> None:
    class Broken:
        name = "broken"

    with pytest.raises(AssertionError, match="config_model"):
        check_collector(Broken)
