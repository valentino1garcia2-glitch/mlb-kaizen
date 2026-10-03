"""Small HTTP client with cache, retries, timeouts and source metadata."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import logging
from pathlib import Path
import time
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from mlb_kaizen.observability.logging import get_logger, log_event

LOGGER = get_logger(__name__)


def _source_host(url: str) -> str:
    """Return scheme+host only; query strings may carry provider credentials."""

    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


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

    def get_json(self, url: str, headers: Mapping[str, str] | None = None) -> RetrievedJson:
        """Fetch a JSON object, using a fresh cached payload when available.

        Authentication headers are never written to the cache payload. Prefer headers for secrets
        such as API keys so cache files cannot accidentally retain credentials.
        """

        cached = self._read_fresh_cache(url)
        if cached is not None:
            return cached

        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                request_headers = {"User-Agent": "MLB-KAIZEN/0.1 (+research)"}
                if headers:
                    request_headers.update(dict(headers))
                request = Request(url, headers=request_headers)
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
                log_event(
                    LOGGER,
                    f"provider request failed on attempt {attempt}/{self.retries}",
                    level=logging.WARNING,
                    operation="http_get_json",
                    source=_source_host(url),
                )
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
            log_event(
                LOGGER,
                f"ignoring unreadable cache entry: {path}",
                level=logging.WARNING,
                operation="cache_read",
            )
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
