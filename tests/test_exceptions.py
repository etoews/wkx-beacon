"""The hierarchy contract: every beacon exception is catchable as BeaconError."""

import pytest

from wkx_beacon.exceptions import (
    BeaconError,
    CollectError,
    ConfigError,
    NotifyError,
    RenderError,
    StoreError,
)


@pytest.mark.parametrize(
    "exc_type", [ConfigError, CollectError, RenderError, StoreError, NotifyError]
)
def test_all_exceptions_are_beacon_errors(exc_type: type[BeaconError]) -> None:
    assert issubclass(exc_type, BeaconError)
