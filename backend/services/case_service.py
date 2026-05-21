"""案例库服务 — 本地读取 + 图片代理缓存"""

import json
import os
import asyncio

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
CASES_PATH = os.path.join(DATA_DIR, "cases.json")
CASE_IMAGES_DIR = os.path.join(DATA_DIR, "case_images")

# GitHub 图片原始地址（仅用于后端下载）
IMAGES_BASE = "https://raw.githubusercontent.com/freestylefly/awesome-gpt-image-2/main/data/images"


def load_cases() -> list:
    """从本地 JSON 读取全部案例"""
    if not os.path.exists(CASES_PATH):
        return []
    with open(CASES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return data.get("cases", [])
    return data


def get_image_filename(image_path: str) -> str:
    """从 image 字段提取文件名"""
    if not image_path:
        return ""
    if image_path.startswith("http"):
        # 远程 URL 提取文件名
        return os.path.basename(image_path.split("?")[0])
    return os.path.basename(image_path)  # /images/case456.jpg → case456.jpg


async def ensure_image_cache(filename: str) -> str:
    """确保图片已缓存，返回本地路径"""
    os.makedirs(CASE_IMAGES_DIR, exist_ok=True)
    local_path = os.path.join(CASE_IMAGES_DIR, filename)

    if os.path.exists(local_path):
        return f"/api/case-images/{filename}"

    # 从 GitHub 下载
    import httpx
    url = f"{IMAGES_BASE}/{filename}"
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            with open(local_path, "wb") as f:
                f.write(resp.content)
            return f"/api/case-images/{filename}"
    except Exception as e:
        print(f"下载案例图片失败 {filename}: {e}")
        return url  # 降级返回原始 URL
