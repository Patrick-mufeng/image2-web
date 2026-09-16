"""图片处理工具函数"""

import os
import re
import base64
from backend.config import settings


async def download_image(url: str, task_id: str, index: int) -> str:
    """从 URL 下载图片到本地存储"""
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


async def save_base64_image(b64_json: str, task_id: str, index: int) -> str:
    """保存 base64 编码的图片到本地"""
    save_dir = settings.image_save_dir
    os.makedirs(save_dir, exist_ok=True)

    filename = f"{task_id}_{index}.png"
    filepath = os.path.join(save_dir, filename)

    try:
        raw = base64.b64decode(b64_json)
        with open(filepath, "wb") as f:
            f.write(raw)
        return f"/api/images/{filename}"
    except Exception as e:
        print(f"保存 base64 图片失败: {e}")
        return ""


def extract_images_from_payload(result: dict) -> list[dict]:
    """从上游响应提取图片项，统一为 {url} 或 {b64_json} 列表。

    文档中两种 200 结构并存，均需兼容：
      1. 标准 images 结构: {"data": [{url|b64_json}, ...]}（调用方先自行取 data）
      2. chat.completion 结构: {"choices": [{"message": {"content"|"images"}}]}
    """
    items: list[dict] = []
    for choice in (result.get("choices") or []):
        msg = (choice or {}).get("message") or {}
        for im in (msg.get("images") or []):
            url = ""
            if isinstance(im, dict):
                inner = im.get("image_url")
                url = (inner or {}).get("url") if isinstance(inner, dict) else ""
                url = url or im.get("url") or ""
            elif isinstance(im, str):
                url = im
            if not url:
                continue
            if url.startswith("data:"):
                b64 = url.split(",", 1)[-1]
                if b64:
                    items.append({"b64_json": b64})
            else:
                items.append({"url": url})
        content = msg.get("content")
        if isinstance(content, str) and content:
            for u in re.findall(r'https?://[^\s)"\']+', content):
                items.append({"url": u})
            for b64 in re.findall(r'data:image/[^;]+;base64,([A-Za-z0-9+/=\s]+)', content):
                b64 = b64.strip()
                if b64:
                    items.append({"b64_json": b64})
    return items
