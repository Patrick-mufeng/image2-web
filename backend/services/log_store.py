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

    def save_entry(self, entry: dict):
        """保存单条完整日志（请求+响应+错误），持久化到文件"""
        entry["id"] = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "_" + str(len(self._read()))
        entry["time"] = datetime.now(timezone.utc).isoformat()
        records = self._read()
        records.insert(0, entry)
        self._write(records[:200])

        # 同步写入独立错误日志文件
        if entry.get("error") or entry.get("status") == "failed":
            self._save_error_log(entry)

    def _save_error_log(self, entry: dict):
        """将有错误的记录追加到 error_logs.json"""
        err_file = os.path.join("data", "error_logs.json")
        try:
            existing = []
            if os.path.exists(err_file):
                with open(err_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            existing.insert(0, entry)
            # 只保留最近 100 条错误
            with open(err_file, "w", encoding="utf-8") as f:
                json.dump(existing[:100], f, ensure_ascii=False, indent=2)
        except Exception:
            pass


log_store = LogStore()
