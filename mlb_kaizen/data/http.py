"""Small HTTP client with cache, retries, timeouts and source metadata."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import logging
from pathlib import Path
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


LOGGER = logging.getLogger(__name__)


class DataProviderError(RuntimeError):
    """A provider could not return a verified response."""


@dataclass(frozen=True, slots=True)
class RetrievedJson:
    """JSON payload plus the timestamp at which it was obtained."""

    payload: dict[str, Any]
    url: str
    retrieved_at: datetime
    from_cache: bool


class CachedHttpClient:
    """HTTP JSON client that caches successful responses only.

    Cached objects contain their retrieval time. A stale cache is never presented
    as fresh data: callers receive a new request or a :class:`DataProviderError`.
    """

    def __init__(
        self,
        cache_dir: Path,
        timeout_seconds: float = 12.0,
        retries: int = 3,
        cache_ttl_seconds: int = 900,
    ) -> None:
        if timeout_seconds <= 0 or retries < 1 or cache_ttl_seconds < 0:
            raise ValueError("invalid HTTP client configuration")
        self.cache_dir = cache_dir
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)

    def get_json(self, url: str) -> RetrievedJson:
        """Fetch a JSON object, using a fresh cached payload when available."""

        cached = self._read_fresh_cache(url)
        if cached is not None:
            return cached

        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                request = Request(url, headers={"User-Agent": "MLB-KAIZEN/0.1 (+research)"})
                with urlopen(request, timeout=self.timeout_seconds) as response:  # nosec B310
                    if response.status != 200:
                        raise DataProviderError(f"unexpected HTTP status {response.status}")
                    decoded = json.loads(response.read().decode("utf-8"))
                if not isinstance(decoded, dict):
                    raise DataProviderError("expected a JSON object")
                retrieved_at = datetime.now(UTC)
                result = RetrievedJson(decoded, url, retrieved_at, from_cache=False)
                self._write_cache(result)
                return result
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, DataProviderError) as exc:
                last_error = exc
                LOGGER.warning("provider request failed", extra={"url": url, "attempt": attempt})
                if attempt < self.retries:
                    time.sleep(0.4 * (2 ** (attempt - 1)))

        raise DataProviderError(f"DATA NOT VERIFIED for {url}: {last_error}") from last_error

    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / f"{sha256(url.encode('utf-8')).hexdigest()}.json"

    def _read_fresh_cache(self, url: str) -> RetrievedJson | None:
        path = self._cache_path(url)
        if not path.exists():
            return None
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            retrieved_at = datetime.fromisoformat(cached["retrieved_at"])
            if datetime.now(UTC) - retrieved_at > self.cache_ttl:
                return None
            payload = cached["payload"]
            if not isinstance(payload, dict):
                return None
            return RetrievedJson(payload, url, retrieved_at, from_cache=True)
        except (KeyError, OSError, ValueError, json.JSONDecodeError):
            LOGGER.warning("ignoring unreadable cache entry", extra={"path": str(path)})
            return None

    def _write_cache(self, result: RetrievedJson) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self._cache_path(result.url)
        serialised = {
            "retrieved_at": result.retrieved_at.isoformat(),
            "url": result.url,
            "payload": result.payload,
        }
        path.write_text(json.dumps(serialised, separators=(",", ":")), encoding="utf-8")
