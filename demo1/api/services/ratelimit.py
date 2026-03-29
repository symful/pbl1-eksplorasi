import asyncio
import hashlib
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Any

logger = logging.getLogger("api.ratelimit")


@dataclass
class RateLimitState:
    source: str
    blocked_until: float = 0.0
    retry_after: float = 60.0
    consecutive_errors: int = 0
    last_error: str = ""


class RateLimitTracker:
    _instance: Optional["RateLimitTracker"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._states = {}
            cls._instance._lock = threading.Lock()
        return cls._instance

    def is_blocked(self, source: str) -> bool:
        with self._lock:
            state = self._states.get(source)
            if state is None:
                return False
            return time.time() < state.blocked_until

    def block(self, source: str, seconds: float, reason: str = ""):
        with self._lock:
            state = self._states.get(source)
            if state is None:
                state = RateLimitState(source=source)
                self._states[source] = state
            state.blocked_until = time.time() + seconds
            state.retry_after = seconds
            state.consecutive_errors += 1
            state.last_error = reason
        logger.warning(f"Rate limited [{source}]: {reason} — blocked for {seconds}s")

    def unblock(self, source: str):
        with self._lock:
            if source in self._states:
                self._states[source].blocked_until = 0.0
                self._states[source].consecutive_errors = 0

    def get_state(self, source: str) -> Optional[RateLimitState]:
        with self._lock:
            return self._states.get(source)

    def check_and_wait(self, source: str) -> float:
        with self._lock:
            state = self._states.get(source)
            if state is None:
                return 0.0
            remaining = state.blocked_until - time.time()
            return max(0.0, remaining)

    async def is_blocked_async(self, source: str) -> bool:
        return self.is_blocked(source)

    async def block_async(self, source: str, seconds: float, reason: str = ""):
        self.block(source, seconds, reason)

    async def unblock_async(self, source: str):
        self.unblock(source)


class RequestCache:
    _instance: Optional["RequestCache"] = None

    @classmethod
    def get_instance(cls) -> "RequestCache":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._cache = {}
            cls._instance._lock = threading.Lock()
            cls._instance._async_lock = asyncio.Lock()
            cls._instance._inflight = {}
        return cls._instance

    def _key(self, namespace: str, **kwargs) -> str:
        data = f"{namespace}:{sorted(kwargs.items())}"
        return hashlib.md5(data.encode()).hexdigest()

    def get(self, namespace: str, **kwargs) -> Optional[Any]:
        key = self._key(namespace, **kwargs)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if time.time() > entry["expires_at"]:
                del self._cache[key]
                return None
            return entry["value"]

    def set(self, namespace: str, value: Any, ttl: float = 60.0, **kwargs):
        key = self._key(namespace, **kwargs)
        with self._lock:
            self._cache[key] = {
                "value": value,
                "expires_at": time.time() + ttl,
                "created_at": time.time(),
            }

    async def get_async(self, namespace: str, **kwargs) -> Optional[Any]:
        key = self._key(namespace, **kwargs)
        async with self._async_lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if time.time() > entry["expires_at"]:
                del self._cache[key]
                return None
            return entry["value"]

    async def set_async(self, namespace: str, value: Any, ttl: float = 60.0, **kwargs):
        key = self._key(namespace, **kwargs)
        async with self._async_lock:
            self._cache[key] = {
                "value": value,
                "expires_at": time.time() + ttl,
                "created_at": time.time(),
            }

    def invalidate(self, namespace: str, **kwargs):
        key = self._key(namespace, **kwargs)
        with self._lock:
            self._cache.pop(key, None)

    def clear(self):
        with self._lock:
            self._cache.clear()
            self._inflight.clear()
