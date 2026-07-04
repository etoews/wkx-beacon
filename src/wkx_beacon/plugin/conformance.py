"""Conformance checks for plugin authors. The plugin API is the product; these are its tests."""

from pydantic import BaseModel


def _check_common(cls: type, kind: str) -> None:
    name = getattr(cls, "name", None)
    assert isinstance(name, str) and name, f"{kind} needs a str name"
    model = getattr(cls, "config_model", None)
    assert isinstance(model, type) and issubclass(model, BaseModel), (
        f"{kind} {cls.__name__} needs a config_model (pydantic BaseModel subclass)"
    )
    assert model.model_config.get("extra") == "forbid", (
        f"{kind} {cls.__name__} config_model must set extra='forbid' so config typos fail at boot"
    )


def check_collector(cls: type) -> None:
    _check_common(cls, "collector")
    assert isinstance(getattr(cls, "report_type", None), str), "collector needs a report_type"
    assert isinstance(getattr(cls, "platform", None), str), "collector needs a platform"
    assert callable(getattr(cls, "collect", None)), "collector needs collect()"
    assert callable(getattr(cls, "template_dir", None)), "collector needs template_dir()"


def check_renderer(cls: type) -> None:
    _check_common(cls, "renderer")
    assert callable(getattr(cls, "render", None)), "renderer needs render()"


def check_notifier(cls: type) -> None:
    _check_common(cls, "notifier")
    assert callable(getattr(cls, "notify", None)), "notifier needs notify()"
