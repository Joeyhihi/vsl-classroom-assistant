from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from vsl_backend.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_defaults_are_dev_mock_loopback(settings_factory: Callable[..., Settings]) -> None:
    s = settings_factory()

    assert (s.env, s.model_mode, s.host) == ("dev", "mock", "127.0.0.1")


def test_mock_mode_refused_outside_dev(settings_factory: Callable[..., Settings]) -> None:
    with pytest.raises(ValidationError, match="mock model mode requires VSL_ENV=dev"):
        settings_factory(env="prod", model_mode="mock")


def test_prod_with_real_model_mode_is_allowed(settings_factory: Callable[..., Settings]) -> None:
    assert settings_factory(env="prod", model_mode="onnx").env == "prod"


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.10", "example.com"])
def test_non_loopback_host_refused(settings_factory: Callable[..., Settings], host: str) -> None:
    with pytest.raises(ValidationError, match="loopback"):
        settings_factory(host=host)


def test_origin_list_parsing(settings_factory: Callable[..., Settings]) -> None:
    s = settings_factory(allowed_origins=" http://a:1 , ,http://b:2 ")

    assert s.allowed_origin_list == ["http://a:1", "http://b:2"]


def test_empty_model_id_becomes_none(settings_factory: Callable[..., Settings]) -> None:
    assert settings_factory(sign_model_id="").sign_model_id is None


def test_default_data_root_is_outside_repository(
    settings_factory: Callable[..., Settings],
) -> None:
    data_root = settings_factory().resolved_data_root.resolve()

    assert REPO_ROOT not in data_root.parents and data_root != REPO_ROOT


def test_env_vars_are_read_with_prefix(
    monkeypatch: pytest.MonkeyPatch, settings_factory: Callable[..., Settings]
) -> None:
    monkeypatch.setenv("VSL_PORT", "8123")

    assert settings_factory().port == 8123
