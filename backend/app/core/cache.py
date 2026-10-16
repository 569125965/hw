from __future__ import annotations

import time
from threading import Lock
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    def __init__(self, ttl_seconds: int = 300) -> None:
        self.ttl = ttl_seconds
        self._store: dict[str, tuple[float, T]] = {}
        self._lock = Lock()

    def get(self, key: str) -> T | None:
        with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            expires_at, value = item
            if time.time() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: T) -> None:
        with self._lock:
            self._store[key] = (time.time() + self.ttl, value)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


def _ttl() -> int:
    import os

    return int(os.getenv("ASHARE_CACHE_TTL", "120"))


class EnvTTLCache(TTLCache[Any]):
    def set(self, key: str, value: Any) -> None:  # type: ignore[override]
        self.ttl = _ttl()
        super().set(key, value)


cache: EnvTTLCache = EnvTTLCache(ttl_seconds=_ttl())
