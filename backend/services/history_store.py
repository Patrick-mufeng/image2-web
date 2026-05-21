"""历史记录存储 — JSON 文件"""

import json
import os
import threading
from datetime import datetime, timezone


class HistoryStore:
    def __init__(self):
        self.file_path = os.path.join("data", "history.json")
        self._lock = threading.Lock()
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(self.file_path):
            self._write([])

    def _read(self) -> list:
        with self._lock:
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return []

    def _write(self, data: list):
        with self._lock:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    def add(self, record: dict):
        record["created_at"] = datetime.now(timezone.utc).isoformat()
        records = self._read()
        records.insert(0, record)
        self._write(records[:200])

    def list(self, page: int = 1, limit: int = 20) -> dict:
        records = self._read()
        total = len(records)
        start = (page - 1) * limit
        return {
            "total": total,
            "page": page,
            "limit": limit,
            "records": records[start: start + limit],
        }

    def clear(self):
        self._write([])


history_store = HistoryStore()
