from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from threading import Lock
from typing import Any


DEFAULT_CACHE_PATH = Path(__file__).resolve().parents[1] / ".cache" / "summary_cache.json"


class SummaryCache:
    def __init__(self, path: Path = DEFAULT_CACHE_PATH):
        self.path = path
        self._lock = Lock()

    def get(
        self,
        *,
        root: Path,
        file_id: str,
        content_hash: str,
        provider: str,
        prompt_version: str,
    ) -> dict[str, Any] | None:
        with self._lock:
            cache = self._read()

        record = cache.get(self._key(root, file_id, provider, prompt_version))

        if not record:
            return None

        if record.get("content_hash") != content_hash:
            return None

        return {**record, "cached": True}

    def set(
        self,
        *,
        root: Path,
        file_id: str,
        content_hash: str,
        provider: str,
        model: str,
        prompt_version: str,
        summary: str,
    ) -> dict[str, Any]:
        record = {
            "root": str(root),
            "file_id": file_id,
            "content_hash": content_hash,
            "provider": provider,
            "model": model,
            "prompt_version": prompt_version,
            "summary": summary,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "cached": False,
        }

        with self._lock:
            cache = self._read()
            cache[self._key(root, file_id, provider, prompt_version)] = record
            self._write(cache)

        return record

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}

        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _write(self, cache: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(cache, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temp_path.replace(self.path)

    @staticmethod
    def _key(root: Path, file_id: str, provider: str, prompt_version: str) -> str:
        raw_key = f"{root.resolve()}::{file_id}::{provider}::{prompt_version}"
        return sha256(raw_key.encode("utf-8")).hexdigest()
