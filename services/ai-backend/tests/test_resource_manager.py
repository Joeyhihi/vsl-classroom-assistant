"""ResourceManager rules with fake engines, a fake clock and a fake memory probe."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from tests.conftest import ALLOWED_ORIGIN
from vsl_backend.inference.resource_manager import ResourceExhausted, ResourceManager


class FakeEngine:
    def __init__(self, name: str, heavy: bool = True) -> None:
        self.name = name
        self.heavy = heavy
        self.loads = 0
        self.unloads = 0

    def load(self) -> None:
        self.loads += 1

    def unload(self) -> None:
        self.unloads += 1


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def manager(free: float = 8000.0, clock: Clock | None = None) -> ResourceManager:
    return ResourceManager(
        idle_unload_s=300, min_free_ram_mb=1500, free_ram=lambda: free, clock=clock or Clock()
    )


def test_lazy_load_on_first_use_only() -> None:
    rm, stt = manager(), FakeEngine("stt")
    rm.register(stt)
    assert stt.loads == 0 and not rm.status()[0].resident

    rm.acquire("stt")
    rm.acquire("stt")
    assert stt.loads == 1 and rm.status()[0].resident


def test_idle_heavy_engines_are_unloaded() -> None:
    clock = Clock()
    rm, stt, sign = manager(clock=clock), FakeEngine("stt"), FakeEngine("sign", heavy=False)
    rm.register(stt)
    rm.register(sign)
    rm.acquire("stt")
    rm.acquire("sign")

    clock.t = 299.0
    assert rm.sweep() == []
    clock.t = 300.0
    assert rm.sweep() == ["stt"]
    assert stt.unloads == 1 and sign.unloads == 0  # the tiny sign model stays resident


def test_use_resets_the_idle_timer() -> None:
    clock = Clock()
    rm, stt = manager(clock=clock), FakeEngine("stt")
    rm.register(stt)
    rm.acquire("stt")
    clock.t = 200.0
    rm.acquire("stt")
    clock.t = 400.0
    assert rm.sweep() == []


def test_ram_guard_refuses_and_leaves_nothing_loaded() -> None:
    rm, stt = manager(free=900.0), FakeEngine("stt")
    rm.register(stt)

    with pytest.raises(ResourceExhausted) as caught:
        rm.acquire("stt")
    assert caught.value.available_mb == 900.0 and stt.loads == 0
    assert not rm.status()[0].resident


def test_swap_rule_keeps_one_heavy_engine() -> None:
    rm, stt, tts = manager(), FakeEngine("stt"), FakeEngine("tts")
    sign = FakeEngine("sign", heavy=False)
    for engine in (stt, tts, sign):
        rm.register(engine)
    rm.acquire("sign")
    rm.acquire("stt")
    rm.acquire("tts")

    resident = {s.name for s in rm.status() if s.resident}
    assert resident == {"sign", "tts"}
    assert stt.unloads == 1 and sign.unloads == 0


def test_duplicate_registration_and_shutdown() -> None:
    rm, stt = manager(), FakeEngine("stt")
    rm.register(stt)
    with pytest.raises(ValueError):
        rm.register(FakeEngine("stt"))
    rm.acquire("stt")
    rm.shutdown()
    assert stt.unloads == 1


def test_resource_exhausted_uses_the_error_envelope(
    client_factory: Callable[..., TestClient],
) -> None:
    client = client_factory()
    route = APIRouter()

    @route.get("/api/v1/_test/exhausted")
    async def exhausted() -> None:
        raise ResourceExhausted("stt", 900.4, 1500)

    client.app.include_router(route)  # type: ignore[attr-defined]
    response = client.get("/api/v1/_test/exhausted", headers={"Origin": ALLOWED_ORIGIN})

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "RESOURCE_EXHAUSTED"
    assert error["details"] == {"available_mb": 900, "required_mb": 1500}
