"""Exception hierarchy. Catch BeaconError for anything raised by beacon."""


class BeaconError(Exception):
    """Base class for all wkx-beacon exceptions."""


class ConfigError(BeaconError):
    """Raised when configuration is missing, malformed, or fails validation at boot."""


class CollectError(BeaconError):
    """Raised when a collector fails to gather platform data."""


class RenderError(BeaconError):
    """Raised when a renderer fails to produce artefacts."""


class StoreError(BeaconError):
    """Raised when the store cannot write or read runs."""


class NotifyError(BeaconError):
    """Raised when a notifier fails to announce a run."""
