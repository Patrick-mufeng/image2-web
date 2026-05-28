"""图片处理工具函数"""

import os
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
