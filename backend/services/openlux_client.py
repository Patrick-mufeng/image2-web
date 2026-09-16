"""OpenLux API 异步 HTTP 客户端
支持两种格式:
  1. OpenAI 兼容格式: POST /v1/images/generations — 即时返回
  2. Replicate 格式:   POST /replicate/v1/models/{model}/predictions — 异步任务 + 轮询（预留）
"""

import asyncio
import json as json_module
import time
import traceback
import httpx
from backend.config import settings


class OpenLuxAPIError(Exception):
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


class OpenLuxClient:
    """OpenLux API 客户端"""

    def __init__(self):
        self._timeout = 500.0

    @staticmethod
    def _normalize_base() -> str:
        """规范化 Base URL：去尾部斜杠；旧配置可能带 /v1 后缀，去掉避免拼出 /v1/v1/..."""
        base = settings.openlux_base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        return base

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {settings.openlux_api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _safe_json(resp, req_info: dict) -> dict:
        """安全解析 JSON 响应，失败时抛出 OpenLuxAPIError"""
        resp_info = {
            "status": resp.status_code,
            "headers": dict(resp.headers),
            "body": resp.text[:2000],
        }
        try:
            return resp.json()
        except (json_module.JSONDecodeError, ValueError) as e:
            raise OpenLuxAPIError(
                f"API 返回非 JSON 响应 ({resp.status_code}): {resp.text[:300]}",
                request_info=req_info,
                response_info=resp_info,
            ) from e

    # ── OpenAI 格式：即时返回 ──────────────────────────────────────

    async def openai_generate(self, prompt: str, model: str = "gpt-image-2",
                               size: str = "1024x1024", n: int = 1,
                               quality: str | None = None,
                               output_format: str | None = None) -> dict:
        """调用 OpenAI 兼容的 /v1/images/generations 接口（即时返回）
        上游可能返回 429「系统繁忙」，自动退避重试（5s / 10s / 20s）；
        遇 400/422 参数错误时自动回退最小参数集（model/prompt/size）重试一次。
        n 仅在 >1 时发送（部分 -c 渠道不支持 n 参数）；quality/format 由调用方按模型能力过滤后传入。"""
        base_url = self._normalize_base()

        payload = {
            "model": model,
            "prompt": prompt,
            "size": size,
        }
        if n and n > 1:
            payload["n"] = n
        if quality:
            payload["quality"] = quality
        if output_format:
            payload["format"] = output_format
        minimal_payload = {"model": model, "prompt": prompt, "size": size}

        url = f"{base_url}/v1/images/generations"
        req_info = {
            "method": "POST",
            "url": url,
            "headers": {k: v[:50] for k, v in self._headers().items()},
            "body": payload,
        }

        max_retries = 3  # 429 上游繁忙时的自动重试次数
        retried = 0
        used_fallback = False

        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(url, headers=self._headers(), json=payload)
            except httpx.TimeoutException as e:
                raise OpenLuxAPIError(f"OpenAI 生图超时（超过 {self._timeout}s），请降低分辨率或重试", request_info=req_info) from e
            except httpx.ConnectError as e:
                raise OpenLuxAPIError(f"无法连接 API 服务器，请检查 Base URL 和网络", request_info=req_info) from e
            except httpx.HTTPError as e:
                raise OpenLuxAPIError(f"网络请求异常: {e}", request_info=req_info) from e

            resp_info = {
                "status": resp.status_code,
                "headers": dict(resp.headers),
                "body": resp.text[:2000],
            }

            # 参数被上游拒绝 → 回退最小参数集重试一次
            if resp.status_code in (400, 422) and not used_fallback and payload != minimal_payload:
                used_fallback = True
                payload = dict(minimal_payload)
                req_info["body"] = payload
                continue

            if resp.status_code == 429 and attempt < max_retries:
                retried += 1
                await asyncio.sleep(5 * (2 ** attempt))  # 5s / 10s / 20s
                continue

            if resp.status_code != 200:
                busy_hint = "（上游繁忙，已自动重试 %d 次，请稍后再试）" % retried if resp.status_code == 429 else ""
                raise OpenLuxAPIError(
                    f"OpenAI 生图失败 ({resp.status_code}): {resp.text[:500]}{busy_hint}",
                    request_info=req_info,
                    response_info=resp_info,
                )

            result = self._safe_json(resp, req_info)
            if used_fallback:
                result["_fallback_minimal"] = True
            return result

    # ── Replicate 格式：异步任务 + 轮询（预留，当前无模型走此通道） ──

    async def create_prediction(self, prompt: str, aspect_ratio: str = "1:1",
                                 megapixels: str = "1", num_outputs: int = 1,
                                 output_format: str = "jpg", output_quality: int = 80,
                                 num_inference_steps: int = 4,
                                 model: str = "black-forest-labs/flux-schnell") -> dict:
        """创建 Replicate 格式预测任务"""
        base_url = self._normalize_base()

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

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, headers=self._headers(), json=payload)
        except httpx.TimeoutException as e:
            raise OpenLuxAPIError(f"创建任务超时，请重试", request_info=req_info) from e
        except httpx.ConnectError as e:
            raise OpenLuxAPIError(f"无法连接 API 服务器", request_info=req_info) from e
        except httpx.HTTPError as e:
            raise OpenLuxAPIError(f"网络请求异常: {e}", request_info=req_info) from e

        resp_info = {"status": resp.status_code, "headers": dict(resp.headers), "body": resp.text[:2000]}

        if resp.status_code not in (200, 201):
            raise OpenLuxAPIError(
                f"创建任务失败 ({resp.status_code}): {resp.text[:500]}",
                request_info=req_info, response_info=resp_info,
            )

        return self._safe_json(resp, req_info)

    async def get_prediction(self, task_id: str) -> dict:
        """查询 Replicate 格式预测任务状态"""
        base_url = self._normalize_base()
        url = f"{base_url}/replicate/v1/predictions/{task_id}"
        req_info = {"method": "GET", "url": url}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url, headers=self._headers())
        except httpx.TimeoutException as e:
            raise OpenLuxAPIError(f"查询任务超时", request_info=req_info) from e
        except httpx.ConnectError as e:
            raise OpenLuxAPIError(f"无法连接 API 服务器", request_info=req_info) from e
        except httpx.HTTPError as e:
            raise OpenLuxAPIError(f"网络请求异常: {e}", request_info=req_info) from e

        resp_info = {"status": resp.status_code, "headers": dict(resp.headers), "body": resp.text[:2000]}

        if resp.status_code != 200:
            raise OpenLuxAPIError(
                f"查询任务失败 ({resp.status_code}): {resp.text[:500]}",
                request_info=req_info, response_info=resp_info,
            )

        return self._safe_json(resp, req_info)

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
                raise OpenLuxAPIError("任务超时 (5分钟)")

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
        """调用 OpenAI 兼容的 /v1/images/edits 接口（multipart 上传）
        上游可能返回 429「系统繁忙」，自动退避重试（5s / 10s / 20s）"""
        base_url = self._normalize_base()
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
        }
        # auto 是上游默认值，省略以兼容不支持该字段的 -c 渠道
        if quality and quality != "auto":
            files["quality"] = (None, quality)
        if background and background != "auto":
            files["background"] = (None, background)

        if mask_data:
            files["mask"] = (mask_filename, mask_data, "image/png")
            req_info["body"]["mask_size"] = len(mask_data)

        headers = {
            "Authorization": f"Bearer {settings.openlux_api_key}",
            "Accept": "application/json",
        }

        max_retries = 3  # 429 上游繁忙时的自动重试次数
        retried = 0

        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(url, headers=headers, files=files)
            except httpx.TimeoutException as e:
                raise OpenLuxAPIError(f"图生图超时，请降低分辨率或重试", request_info=req_info) from e
            except httpx.ConnectError as e:
                raise OpenLuxAPIError(f"无法连接 API 服务器", request_info=req_info) from e
            except httpx.HTTPError as e:
                raise OpenLuxAPIError(f"网络请求异常: {e}", request_info=req_info) from e

            resp_info = {"status": resp.status_code, "headers": dict(resp.headers), "body": resp.text[:2000]}

            if resp.status_code == 429 and attempt < max_retries:
                retried += 1
                await asyncio.sleep(5 * (2 ** attempt))  # 5s / 10s / 20s
                continue

            if resp.status_code != 200:
                busy_hint = "（上游繁忙，已自动重试 %d 次，请稍后再试）" % retried if resp.status_code == 429 else ""
                raise OpenLuxAPIError(
                    f"图生图编辑失败 ({resp.status_code}): {resp.text[:500]}{busy_hint}",
                    request_info=req_info, response_info=resp_info,
                )

            return self._safe_json(resp, req_info)

    # ── OpenAI 格式：多图参考生成 (gpt-image-2-all) ──────────────
    # （已移除：gpt-image-2-all 模型已下线；gpt-image-2-c 直接在
    #   /v1/images/generations 传 image 数组即可实现多图参考）


# 全局单例
openlux_client = OpenLuxClient()