"""任务管理器 — 跟踪生成任务状态，支持后台轮询"""

import time
import asyncio
import json
import os
import threading
import traceback
from datetime import datetime

from backend.config import settings
from backend.services.yunwu_client import yunwu_client, YunwuAPIError


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


async def _download_image(url: str, task_id: str, index: int) -> str:
    """从 URL 下载图片到本地"""
    import httpx
    save_dir = settings.image_save_dir
    os.makedirs(save_dir, exist_ok=True)

    ext = url.split(".")[-1].split("?")[0] or "jpg"
    filename = f"{task_id}_{index}.{ext}"
    filepath = os.path.join(save_dir, filename)

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            with open(filepath, "wb") as f:
                f.write(resp.content)
            return f"/api/images/{filename}"
        except Exception as e:
            print(f"下载图片失败 {url}: {e}")
            return ""


class TaskManager:
    """内存任务状态管理"""

    def __init__(self):
        self._tasks: dict[str, dict] = {}
        self._lock = threading.Lock()

    def _get(self, task_id: str) -> dict:
        with self._lock:
            return dict(self._tasks.get(task_id, {}))

    def _update(self, task_id: str, data: dict):
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].update(data)

    def create(self, task_id: str, initial: dict):
        with self._lock:
            self._tasks[task_id] = initial

    def get(self, task_id: str) -> dict:
        return self._get(task_id)

    def append_log(self, task_id: str, text: str):
        """追加一行日志"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task["logs"] = task.get("logs", "") + text + "\n"

    # ── Replicate 格式后台轮询 ──────────────────────────────

    async def start_replicate_polling(self, task_id: str, prompt: str,
                                       aspect_ratio: str, megapixels: str,
                                       num_outputs: int, output_format: str,
                                       output_quality: int, num_inference_steps: int,
                                       model: str, request_data: dict):
        """后台轮询 Replicate 任务状态，逐步更新日志"""
        t0 = time.time()
        save_dir = settings.image_save_dir
        os.makedirs(save_dir, exist_ok=True)

        self.append_log(task_id, f"[{_ts()}] 📤 创建 Replicate 预测任务...")
        self.append_log(task_id, f"模型: {model} | 比例: {aspect_ratio} | 分辨率: {megapixels}MP")

        try:
            # 1. 创建任务
            self.append_log(task_id, f"[{_ts()}] 请求中...")
            prediction = await yunwu_client.create_prediction(
                prompt=prompt, aspect_ratio=aspect_ratio,
                megapixels=megapixels, num_outputs=num_outputs,
                output_format=output_format, output_quality=output_quality,
                num_inference_steps=num_inference_steps, model=model,
            )

            rid = prediction.get("id", task_id)
            initial_status = prediction.get("status", "starting")
            self._update(task_id, {"task_id": rid})
            self.append_log(task_id, f"[{_ts()}] ✅ 任务创建成功: {rid}")
            self.append_log(task_id, f"[{_ts()}] 初始状态: {initial_status}")

            # 如果已经完成则直接处理
            if initial_status in ("succeeded", "failed", "canceled"):
                await self._handle_replicate_result(task_id, prediction, rid, t0, request_data,
                                                     num_outputs, save_dir)
                return

            # 2. 轮询
            self.append_log(task_id, f"[{_ts()}] ⏳ 等待生成...")
            last_log_len = 0

            while True:
                data = await yunwu_client.get_prediction(rid)
                status = data.get("status", "")

                # 追加新增日志
                logs_chunk = data.get("logs", "")
                if logs_chunk and len(logs_chunk) > last_log_len:
                    new_part = logs_chunk[last_log_len:]
                    for line in new_part.split("\n"):
                        line = line.strip()
                        if line:
                            self.append_log(task_id, line)
                    last_log_len = len(logs_chunk)

                # 更新状态
                self._update(task_id, {
                    "status": status,
                    "response_data": data,
                })

                if status in ("succeeded", "failed", "canceled"):
                    await self._handle_replicate_result(task_id, data, rid, t0, request_data,
                                                         num_outputs, save_dir)
                    return

                if time.time() - t0 > 300:
                    self.append_log(task_id, f"[{_ts()}] ❌ 任务超时 (5分钟)")
                    self._update(task_id, {"status": "failed", "error": "超时", "_done": True})
                    return

                await asyncio.sleep(0.8)

        except YunwuAPIError as e:
            self.append_log(task_id, f"[{_ts()}] ❌ API错误: {str(e)}")
            self._update(task_id, {"status": "failed", "error": str(e), "_done": True,
                                   "request_data": request_data})
        except Exception as e:
            self.append_log(task_id, f"[{_ts()}] ❌ 异常: {str(e)}")
            self.append_log(task_id, f"[{_ts()}] 📋 堆栈: {traceback.format_exc()[-500:]}")
            self._update(task_id, {"status": "failed", "error": str(e), "_done": True,
                                   "request_data": request_data})

    async def _handle_replicate_result(self, task_id, data, rid, t0, request_data,
                                        num_outputs, save_dir):
        """处理 Replicate 完成结果"""
        status = data.get("status", "unknown")
        elapsed = time.time() - t0

        if status == "succeeded":
            self.append_log(task_id, f"[{_ts()}] ✅ 生成成功! 耗时: {elapsed:.1f}s")
            self.append_log(task_id, f"[{_ts()}] 📥 下载图片到本地...")

            output_urls = data.get("output", [])
            if isinstance(output_urls, str):
                output_urls = [output_urls]

            local_images = []
            for idx, url in enumerate(output_urls):
                self.append_log(task_id, f"[{_ts()}]   ({idx+1}/{len(output_urls)}) 下载中...")
                local_path = await _download_image(url, task_id, idx)
                if local_path:
                    local_images.append(local_path)

            self.append_log(task_id, f"[{_ts()}] ✅ 全部完成!")

            self._update(task_id, {
                "status": "succeeded",
                "output": output_urls,
                "local_images": local_images,
                "response_data": data,
                "request_data": request_data,
                "_done": True,
                "_elapsed": elapsed,
            })

            # 存历史
            from backend.services.history_store import history_store
            history_store.add({
                "task_id": task_id, "api_task_id": rid,
                "prompt": request_data.get("prompt", ""),
                "model": request_data.get("model", ""),
                "aspect_ratio": request_data.get("aspect_ratio", "1:1"),
                "megapixels": request_data.get("megapixels", "1"),
                "num_outputs": num_outputs,
                "images": [{"url": u, "local_path": p}
                           for u, p in zip(output_urls, local_images)],
                "status": "succeeded",
            })

            from backend.services.log_store import log_store
            log_store.add({
                "type": "generate", "status": "succeeded",
                "request": request_data, "response_body": data,
                "total_time": elapsed, "error": None,
            })

        else:
            err = data.get("error", status)
            self.append_log(task_id, f"[{_ts()}] ❌ 失败: {err}")
            self._update(task_id, {
                "status": "failed", "error": err,
                "response_data": data, "request_data": request_data,
                "_done": True, "_elapsed": elapsed,
            })


# 全局单例
task_manager = TaskManager()
