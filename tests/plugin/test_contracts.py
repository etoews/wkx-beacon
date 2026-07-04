from fakes import FakeCollector, FakeConfig, FakeNotifier, FakeRenderer

from wkx_beacon.plugin import Collector, Notifier, Renderer


def test_fakes_satisfy_the_protocols() -> None:
    assert isinstance(FakeCollector(FakeConfig()), Collector)
    assert isinstance(FakeRenderer(FakeConfig()), Renderer)
    assert isinstance(FakeNotifier(FakeConfig()), Notifier)
