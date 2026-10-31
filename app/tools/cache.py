"""Persistent last-good ToolResult cache; cache reads never refresh source time."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.schemas import ToolResult

log = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ToolCache:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path, timeout=5) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS tool_cache "
                "(cache_key TEXT PRIMARY KEY, result TEXT NOT NULL)"
            )

    def get(self, key: str, max_age_seconds: float | None = None,
            now: datetime | None = None) -> ToolResult | None:
        try:
            with sqlite3.connect(self.path, timeout=5) as connection:
                row = connection.execute(
                    "SELECT result FROM tool_cache WHERE cache_key = ?", (key,)
                ).fetchone()
            if row is None:
                return None
            result = ToolResult.model_validate_json(row[0])
            if result.error or result.fetched_at.utcoffset() is None:
                return None
            age = ((now or utcnow()) - result.fetched_at).total_seconds()
            if age < -60 or (max_age_seconds is not None and age > max_age_seconds):
                return None
            return result.model_copy(update={"is_cached": True}, deep=True)
        except (sqlite3.Error, ValueError):
            log.warning("Cache read unavailable")
            return None

    def put(self, key: str, result: ToolResult) -> None:
        if result.error or result.confidence not in {"high", "medium"}:
            return
        try:
            with sqlite3.connect(self.path, timeout=5) as connection:
                connection.execute(
                    "INSERT INTO tool_cache(cache_key, result) VALUES (?, ?) "
                    "ON CONFLICT(cache_key) DO UPDATE SET result = excluded.result",
                    (key, result.model_dump_json()),
                )
        except sqlite3.Error:
            log.warning("Cache write unavailable")
