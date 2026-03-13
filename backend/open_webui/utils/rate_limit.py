import time
from typing import Dict


class RateLimiter:
    _memory_store: Dict[str, Dict[int, int]] = {}

    def __init__(
        self,
        limit: int,
        window: int,
        bucket_size: int = 60,
        enabled: bool = True,
    ):
        self.limit = limit
        self.window = window
        self.bucket_size = bucket_size
        self.num_buckets = window // bucket_size
        self.enabled = enabled

    def _current_bucket(self) -> int:
        return int(time.time()) // self.bucket_size

    def is_limited(self, key: str) -> bool:
        if not self.enabled:
            return False

        now_bucket = self._current_bucket()

        if key not in self._memory_store:
            self._memory_store[key] = {}

        store = self._memory_store[key]
        store[now_bucket] = store.get(now_bucket, 0) + 1

        min_bucket = now_bucket - self.num_buckets
        expired = [b for b in store if b < min_bucket]
        for b in expired:
            del store[b]

        return sum(store.values()) > self.limit
