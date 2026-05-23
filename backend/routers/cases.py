"""案例展示 API 路由"""

import os
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse
from backend.services.case_service import load_cases, get_image_filename, ensure_image_cache, CASE_IMAGES_DIR

router = APIRouter()


@router.get("/cases")
async def list_cases(
    category: str = None,
    language: str = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str = None,
):
    """获取案例列表（分页 + 分类 + 语言过滤）"""
    cases = load_cases()

    if category:
        cases = [c for c in cases if c.get("category") == category]
    if language:
        cases = [c for c in cases if c.get("language") == language]
    if search:
        sl = search.lower()
        cases = [c for c in cases if sl in (c.get("title", "") + c.get("prompt", "")).lower()]

    total = len(cases)
    start = (page - 1) * limit
    items = cases[start: start + limit]

    for item in items:
        img = item.get("image", "")
        if img:
            fname = get_image_filename(img)
            item["image_url"] = f"/api/case-images/{fname}" if fname else ""
        prompt = item.get("prompt", "")
        if prompt and len(prompt) > 200:
            item["prompt_short"] = prompt[:200] + "..."

    return {"total": total, "page": page, "limit": limit, "cases": items}


@router.get("/cases/categories")
async def list_case_categories():
    """获取案例的分类及数量（含语言统计）"""
    cases = load_cases()
    counts = {}
    lang_counts = {"zh": 0, "en": 0}
    for c in cases:
        cat = c.get("category", "其他")
        counts[cat] = counts.get(cat, 0) + 1
        lang = c.get("language", "en")
        if lang in lang_counts:
            lang_counts[lang] += 1
    sorted_cats = sorted(counts.items(), key=lambda x: -x[1])
    return {
        "categories": [{"name": k, "count": v} for k, v in sorted_cats],
        "languages": [
            {"name": "中文提示词", "value": "zh", "count": lang_counts["zh"]},
            {"name": "English", "value": "en", "count": lang_counts["en"]},
        ],
    }


@router.get("/case-images/{filename}")
async def get_case_image(filename: str):
    """图片代理 — 从 GitHub 缓存到本地后返回"""
    local_path = os.path.join(CASE_IMAGES_DIR, filename)
    if not os.path.exists(local_path):
        # 尝试下载
        from backend.services.case_service import IMAGES_BASE
        import httpx
        url = f"{IMAGES_BASE}/{filename}"
        try:
            os.makedirs(CASE_IMAGES_DIR, exist_ok=True)
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                with open(local_path, "wb") as f:
                    f.write(resp.content)
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"图片下载失败: {filename}")

    return FileResponse(local_path, media_type="image/jpeg")
