"""
Abstract base class for enrichment source adapters.

Provides rate limiting, HTTP retry logic, incremental fetch tracking,
and the enrich() orchestration cycle: should_fetch → fetch → store → log.
"""
from __future__ import annotations

import hashlib
import sqlite3
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json


@dataclass
class AdapterConfig:
    source_name: str
    base_url: str
    rate_limit: float = 3.0      # max requests per second
    retries: int = 3
    retry_delay: float = 2.0     # seconds between retries
    email: str = ""              # for polite-pool APIs
    enabled: bool = True
    max_age_days: int = 30
    timeout: int = 30


@dataclass
class FetchResult:
    nct_id: str
    source: str
    status: str            # "ok", "empty", "error", "skipped"
    records: int = 0
    raw_hash: str = ""
    error: str = ""


class BaseAdapter(ABC):
    """Abstract base for all enrichment source adapters."""

    def __init__(self, db_path: Path, config: AdapterConfig) -> None:
        self.db_path = db_path
        self.config = config
        self._last_request_time: float = 0.0

    @property
    def source_name(self) -> str:
        return self.config.source_name

    # ── Rate limiting ────────────────────────────────────────────────

    def _rate_limit(self) -> None:
        """Sleep if needed to respect rate limit."""
        if self.config.rate_limit <= 0:
            return
        min_interval = 1.0 / self.config.rate_limit
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.monotonic()

    # ── HTTP helpers ─────────────────────────────────────────────────

    def _get(self, url: str, headers: Optional[Dict[str, str]] = None) -> bytes:
        """HTTP GET with rate limiting and retry."""
        hdrs = {"User-Agent": self._user_agent()}
        if headers:
            hdrs.update(headers)

        last_error: Optional[Exception] = None
        for attempt in range(self.config.retries):
            self._rate_limit()
            try:
                req = Request(url, headers=hdrs)
                with urlopen(req, timeout=self.config.timeout) as resp:
                    # Guard against unbounded responses (B-7)
                    max_size = 50 * 1024 * 1024  # 50 MB
                    data = resp.read(max_size + 1)
                    if len(data) > max_size:
                        raise ValueError(f"Response too large from {url}: >{max_size} bytes")
                    return data
            except HTTPError as exc:
                last_error = exc
                if exc.code in (429, 403):
                    # Rate limited (429) or transient 403 — back off longer
                    time.sleep(self.config.retry_delay * (attempt + 2))
                elif exc.code >= 500 or exc.code == 408:
                    time.sleep(self.config.retry_delay * (attempt + 1))
                else:
                    raise
            except (URLError, TimeoutError, OSError) as exc:
                last_error = exc
                time.sleep(self.config.retry_delay * (attempt + 1))

        raise last_error or RuntimeError(f"GET {url} failed after {self.config.retries} retries")

    def _get_json(self, url: str, headers: Optional[Dict[str, str]] = None) -> Any:
        """HTTP GET returning parsed JSON. Raises ValueError on malformed response."""
        raw = self._get(url, headers)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            preview = raw[:200].decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)[:200]
            raise ValueError(
                f"Malformed JSON from {url}: {exc}. Response preview: {preview}"
            ) from exc

    def _user_agent(self) -> str:
        agent = "ICU-LivingMap-Enrichment/1.0"
        if self.config.email:
            agent += f" (mailto:{self.config.email})"
        return agent

    @staticmethod
    def _hash_bytes(data: bytes) -> str:
        return f"sha256:{hashlib.sha256(data).hexdigest()}"

    # ── Incremental tracking ─────────────────────────────────────────

    def should_fetch(self, nct_id: str) -> bool:
        """Check if this NCT ID needs fetching (not fetched or stale)."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                """SELECT fetched_utc FROM enrichment_log
                   WHERE nct_id = ? AND source = ? AND status IN ('ok', 'empty')
                   ORDER BY fetched_utc DESC LIMIT 1""",
                (nct_id, self.source_name),
            ).fetchone()
        finally:
            conn.close()

        if row is None:
            return True

        fetched_utc = row[0]
        try:
            fetched_dt = datetime.fromisoformat(fetched_utc)
            if fetched_dt.tzinfo is None:
                fetched_dt = fetched_dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return True

        age_days = (datetime.now(timezone.utc) - fetched_dt).total_seconds() / 86400
        return age_days > self.config.max_age_days

    def log_fetch(self, result: FetchResult) -> None:
        """Write a fetch result to enrichment_log."""
        now = self._now_utc()
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO enrichment_log
                   (nct_id, source, status, records_found, fetched_utc, error_message)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (result.nct_id, result.source, result.status,
                 result.records, now, result.error or None),
            )
            conn.commit()
        finally:
            conn.close()

    def store_hash(self, content_key: str, hash_value: str) -> None:
        """Record a content hash for TruthCert provenance."""
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO source_hashes
                   (source, content_key, hash_value, fetched_utc)
                   VALUES (?, ?, ?, ?)""",
                (self.source_name, content_key, hash_value, now),
            )
            conn.commit()
        finally:
            conn.close()

    # ── Orchestration cycle ──────────────────────────────────────────

    def enrich(self, nct_id: str, context: Dict[str, Any]) -> FetchResult:
        """
        Main enrichment cycle for one trial:
          1. Check if fetch needed (incremental)
          2. Fetch from source
          3. Store results in DB
          4. Log the fetch
        """
        if not self.config.enabled:
            return FetchResult(nct_id, self.source_name, "skipped", error="source disabled")

        if not self.should_fetch(nct_id):
            return FetchResult(nct_id, self.source_name, "skipped", error="fresh data exists")

        try:
            result = self.fetch_for_trial(nct_id, context)
            if result.status == "ok" and result.records > 0:
                self.store_results(result, context)
            self.log_fetch(result)
            return result
        except Exception as exc:
            result = FetchResult(nct_id, self.source_name, "error", error=str(exc))
            self.log_fetch(result)
            return result

    # ── Abstract methods (must be implemented by each adapter) ───────

    @abstractmethod
    def fetch_for_trial(self, nct_id: str, context: Dict[str, Any]) -> FetchResult:
        """Fetch data from the source for a given NCT ID.
        Returns a FetchResult with status and record count.
        The raw data should be stored in context for store_results()."""
        ...

    @abstractmethod
    def store_results(self, result: FetchResult, context: Dict[str, Any]) -> None:
        """Persist fetched data into the enrichment SQLite database."""
        ...

    # ── DB helpers for subclasses ────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout = 30000")
        return conn

    def _now_utc(self) -> str:
        return datetime.now(timezone.utc).isoformat()
