"""云雾API 异步 HTTP 客户端
支持两种格式:
  1. OpenAI 兼容格式: POST /v1/images/generations — 即时返回
  2. Replicate 格式:   POST /replicate/v1/models/{model}/predictions — 异步任务 + 轮询
"""

import asyncio
import time
import httpx
from backend.config import settings


class YunwuAPIError(Exception):
    """上游 API 错误，携带完整请求/响应信息"""

    def __init__(self, message: str, request_info: dict = None, response_info: dict = None):
        super().__init__(message)
        self.request_info = request_info or {}
        self.response_info = response_info or {}

    def to_dict(self) -> dict:
        return {
            "error": str(self),
            "request": self.request_info,
            "response": self.response_info,
        }


class YunwuClient:
    """云雾API 客户端"""

    def __init__(self):
        self._timeout = 120.0

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {settings.yunwu_api_key}",
            "Content-Type": "application/json",
        }

    # ── OpenAI 格式：即时返回 ──────────────────────────────────────

    async def openai_generate(self, prompt: str, model: str = "gpt-image-2",
                               size: str = "1024x1024", n: int = 1) -> dict:
        """调用 OpenAI 兼容的 /v1/images/generations 接口（即时返回）"""
        base_url = settings.yunwu_base_url.rstrip("/")

        payload = {
            "model": model,
            "prompt": prompt,
            "n": n,
            "size": size,
        }

        url = f"{base_url}/v1/images/generations"
        req_info = {
            "method": "POST",
            "url": url,
            "headers": {k: v[:50] for k, v in self._headers().items()},
            "body": payload,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, headers=self._headers(), json=payload)
            resp_info = {
                "status": resp.status_code,
                "headers": dict(resp.headers),
                "body": resp.text[:2000],
            }

            if resp.status_code != 200:
                raise YunwuAPIError(
                    f"OpenAI 生图失败 ({resp.status_code}): {resp.text[:500]}",
                    request_info=req_info,
                    response_info=resp_info,
                )

            return resp.json()

    # ── Replicate 格式：异步任务 + 轮询 ────────────────────────────

    async def create_prediction(self, prompt: str, aspect_ratio: str = "1:1",
                                 megapixels: str = "1", num_outputs: int = 1,
                                 output_format: str = "jpg", output_quality: int = 80,
                                 num_inference_steps: int = 4,
                                 model: str = "black-forest-labs/flux-schnell") -> dict:
        """创建 Replicate 格式预测任务"""
        base_url = settings.yunwu_base_url.rstrip("/")

        payload = {
            "input": {
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "megapixels": megapixels,
                "num_outputs": num_outputs,
                "output_format": output_format,
                "output_quality": output_quality,
                "num_inference_steps": num_inference_steps,
            }
        }

        url = f"{base_url}/replicate/v1/models/{model}/predictions"
        req_info = {"method": "POST", "url": url, "headers": {k: v[:50] for k, v in self._headers().items()}, "body": payload}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, headers=self._headers(), json=payload)
            resp_info = {"status": resp.status_code, "headers": dict(resp.headers), "body": resp.text[:2000]}

            if resp.status_code not in (200, 201):
                raise YunwuAPIError(
                    f"创建任务失败 ({resp.status_code}): {resp.text[:500]}",
                    request_info=req_info, response_info=resp_info,
                )

            return resp.json()

    async def get_prediction(self, task_id: str) -> dict:
        """查询 Replicate 格式预测任务状态"""
        base_url = settings.yunwu_base_url.rstrip("/")
        url = f"{base_url}/replicate/v1/predictions/{task_id}"
        req_info = {"method": "GET", "url": url}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, headers=self._headers())
            resp_info = {"status": resp.status_code, "headers": dict(resp.headers), "body": resp.text[:2000]}

            if resp.status_code != 200:
                raise YunwuAPIError(
                    f"查询任务失败 ({resp.status_code}): {resp.text[:500]}",
                    request_info=req_info, response_info=resp_info,
                )

            return resp.json()

    async def wait_for_completion(self, task_id: str, on_progress=None,
                                   poll_interval: float = 0.5) -> dict:
        """轮询等待 Replicate 任务完成"""
        t0 = time.time()

        while True:
            data = await self.get_prediction(task_id)
            status = data.get("status", "")

            if on_progress:
                on_progress({
                    "status": status,
                    "logs": data.get("logs", ""),
                    "elapsed": time.time() - t0,
                })

            if status in ("succeeded", "failed", "canceled"):
                data["_elapsed"] = time.time() - t0
                return data

            if time.time() - t0 > 300:
                raise YunwuAPIError("任务超时 (5分钟)")

            await asyncio.sleep(poll_interval)


    # ── OpenAI 格式：图生图编辑 ────────────────────────────────────

    async def edit_image(self, image_data: bytes, prompt: str,
                          filename: str = "image.png",
                          model: str = "gpt-image-2",
                          mask_data: bytes | None = None,
                          mask_filename: str = "mask.png",
                          n: int = 1,
                          size: str = "1024x1024",
                          quality: str = "auto",
                          background: str = "auto") -> dict:
        """调用 OpenAI 兼容的 /v1/images/edits 接口（multipart 上传）"""
        base_url = settings.yunwu_base_url.rstrip("/")
        url = f"{base_url}/v1/images/edits"

        req_info = {
            "method": "POST",
            "url": url,
            "body": {"prompt": prompt, "model": model, "n": n, "size": size, "quality": quality, "background": background, "image_size": len(image_data)},
        }

        files = {
            "image": (filename, image_data, "image/png"),
            "prompt": (None, prompt),
            "model": (None, model),
            "n": (None, str(n)),
            "size": (None, size),
            "quality": (None, quality),
            "background": (None, background),
        }

        if mask_data:
            files["mask"] = (mask_filename, mask_data, "image/png")
            req_info["body"]["mask_size"] = len(mask_data)

        headers = {
            "Authorization": f"Bearer {settings.yunwu_api_key}",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, headers=headers, files=files)
            resp_info = {"status": resp.status_code, "headers": dict(resp.headers), "body": resp.text[:2000]}

            if resp.status_code != 200:
                raise YunwuAPIError(
                    f"图生图编辑失败 ({resp.status_code}): {resp.text[:500]}",
                    request_info=req_info, response_info=resp_info,
                )

            return resp.json()

    # ── OpenAI 格式：多图参考生成 (gpt-image-2-all) ──────────────

    async def reference_generate(self, prompt: str, image_urls: list[str],
                                  model: str = "gpt-image-2-all",
                                  size: str = "1024x1024", n: int = 1) -> dict:
        """调用 gpt-image-2-all 多图参考生成接口"""
        base_url = settings.yunwu_base_url.rstrip("/")

        payload = {
            "model": model,
            "prompt": prompt,
            "n": n,
            "size": size,
            "image": image_urls,
        }

        url = f"{base_url}/v1/images/generations"
        req_info = {"method": "POST", "url": url, "headers": {k: v[:50] for k, v in self._headers().items()}, "body": payload}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, headers=self._headers(), json=payload)
            resp_info = {"status": resp.status_code, "headers": dict(resp.headers), "body": resp.text[:2000]}

            if resp.status_code != 200:
                raise YunwuAPIError(
                    f"多图参考生成失败 ({resp.status_code}): {resp.text[:500]}",
                    request_info=req_info, response_info=resp_info,
                )

            return resp.json()


# 全局单例
yunwu_client = YunwuClient()
