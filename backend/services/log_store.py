"""请求日志存储 — JSON 文件"""

import json
import os
import threading
from datetime import datetime, timezone


class LogStore:
    def __init__(self):
        self.file_path = os.path.join("data", "request_logs.json")
        self._lock = threading.Lock()
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(self.file_path):
            self._write([])

    def _read(self):
        with self._lock:
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return []

    def _write(self, data):
        with self._lock:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    def add(self, entry: dict):
        entry["id"] = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "_" + str(len(self._read()))
        entry["time"] = datetime.now(timezone.utc).isoformat()
        records = self._read()
        records.insert(0, entry)
        self._write(records[:200])

    def get_recent(self, limit=50):
        return self._read()[:limit]

    def clear(self):
        self._write([])


log_store = LogStore()
