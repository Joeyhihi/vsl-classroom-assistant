"""ResourceManager (ADR-015): lazy load, idle unload, RAM guard and the swap rule.

The sign model is tiny and stays resident. Heavy engines (STT from P7, and any
post-MVP backend TTS or GPU model) are registered here and are:

- loaded on first `acquire`, never at start-up;
- unloaded by `sweep` after `idle_unload_s` without use;
- refused with RESOURCE_EXHAUSTED when free RAM is below `min_free_ram_mb`;
- swapped: loading one heavy engine first unloads any other resident heavy engine.

Engines are plain objects with `load()` / `unload()`, so the rules are unit-tested
with fakes on the M1 (no model is ever loaded there).
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import psutil

logger = logging.getLogger(__name__)


class Engine(Protocol):
    name: str
    heavy: bool

    def load(self) -> None: ...

    def unload(self) -> None: ...


class ResourceExhausted(Exception):
    def __init__(self, engine: str, available_mb: float, required_mb: float) -> None:
        super().__init__(f"not enough free memory to load {engine}")
        self.engine = engine
        self.available_mb = available_mb
        self.required_mb = required_mb


@dataclass
class _Slot:
    engine: Engine
    resident: bool = False
    last_used: float = 0.0


@dataclass(frozen=True)
class EngineStatus:
    name: str
    heavy: bool
    resident: bool
    idle_s: float | None


def free_ram_mb() -> float:
    return float(psutil.virtual_memory().available) / 2**20


class ResourceManager:
    def __init__(
        self,
        idle_unload_s: float,
        min_free_ram_mb: float,
        free_ram: Callable[[], float] = free_ram_mb,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.idle_unload_s = idle_unload_s
        self.min_free_ram_mb = min_free_ram_mb
        self._free_ram = free_ram
        self._clock = clock
        self._slots: dict[str, _Slot] = {}
        self._lock = threading.RLock()

    def register(self, engine: Engine) -> None:
        with self._lock:
            if engine.name in self._slots:
                raise ValueError(f"engine {engine.name!r} is already registered")
            self._slots[engine.name] = _Slot(engine)

    def acquire(self, name: str) -> Engine:
        """Return a loaded engine, loading it (and swapping out other heavy ones) if needed."""
        with self._lock:
            slot = self._slots[name]
            if not slot.resident:
                if slot.engine.heavy:
                    for other in self._slots.values():
                        if other is not slot and other.engine.heavy and other.resident:
                            self._unload(other, "swap")
                available = self._free_ram()
                if available < self.min_free_ram_mb:
                    raise ResourceExhausted(name, available, self.min_free_ram_mb)
                slot.engine.load()
                slot.resident = True
                logger.info("loaded %s", name)
            slot.last_used = self._clock()
            return slot.engine

    def release(self, name: str) -> None:
        with self._lock:
            slot = self._slots.get(name)
            if slot and slot.resident:
                self._unload(slot, "release")

    def sweep(self) -> list[str]:
        """Unload heavy engines idle for longer than `idle_unload_s`. Returns their names."""
        now = self._clock()
        unloaded = []
        with self._lock:
            for slot in self._slots.values():
                idle = now - slot.last_used
                if slot.engine.heavy and slot.resident and idle >= self.idle_unload_s:
                    self._unload(slot, "idle")
                    unloaded.append(slot.engine.name)
        return unloaded

    def status(self) -> list[EngineStatus]:
        now = self._clock()
        with self._lock:
            return [
                EngineStatus(
                    s.engine.name,
                    s.engine.heavy,
                    s.resident,
                    round(now - s.last_used, 1) if s.resident else None,
                )
                for s in self._slots.values()
            ]

    def shutdown(self) -> None:
        with self._lock:
            for slot in self._slots.values():
                if slot.resident:
                    self._unload(slot, "shutdown")

    def _unload(self, slot: _Slot, reason: str) -> None:
        try:
            slot.engine.unload()
        finally:
            slot.resident = False
            logger.info("unloaded %s (%s)", slot.engine.name, reason)
