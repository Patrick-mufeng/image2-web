"""模型目录服务 — 动态拉取线上「模型 × 分组 × 费率」

数据源（2026-09 实测）：
  1. GET {base}/v1/models     需 Bearer，返回当前令牌实际可用的模型（含 model_type/description）
  2. GET {base}/api/pricing   公开接口，返回全部模型的 enable_groups / 按次单价 / quota_type
                              以及 group_ratio 分组费率表

分组是令牌级属性（建令牌时选定，网关按令牌分组路由渠道），请求本身不传分组；
前端分组下拉仅用于筛选与费率预估。拉取失败时回退到内置表。
"""

import asyncio
import time

import httpx

from backend.config import settings

TTL = 600  # 缓存 10 分钟

# 仅支持固定档位尺寸的模型（文档：gpt-image-2-c 必须是 1024x1024 / 1536x1024 / 1024x1536）
SIZE_1K_TIERS = ["1024x1024", "1536x1024", "1024x1536"]

# ── 内置兜底表（与线上实测一致；仅当两个接口都拉不到时使用）────────────
FALLBACK_MODELS = [
    {"value": "gpt-image-2.5-flare-c", "label": "GPT Image 2.5 Flare (推荐)", "group": "✨ GPT Image · 即时返回",
     "supported_groups": ["Gpt-Image-1", "Gpt-Image-2", "Gpt-Image-3"],
     "capabilities": {"n": True, "quality": ["auto", "low", "medium", "high", "xhigh", "max"], "format": True}},
    {"value": "gpt-image-2.5-sunburst-c", "label": "GPT Image 2.5 Sunburst (精修)", "group": "✨ GPT Image · 即时返回",
     "supported_groups": ["Gpt-Image-1", "Gpt-Image-2", "Gpt-Image-3"],
     "capabilities": {"n": True, "quality": ["auto", "low", "medium", "high", "xhigh", "max"], "format": True}},
    {"value": "gpt-image-2-c", "label": "GPT Image 2-C", "group": "✨ GPT Image · 即时返回",
     "supported_groups": ["Gpt-Image-1", "Gpt-Image-2"],
     "capabilities": {"n": False, "quality": ["auto"], "format": False, "fixed_sizes": list(SIZE_1K_TIERS)}},
]

FALLBACK_GROUPS = [
    {"value": "Gpt-Image-1", "label": "Gpt-Image-1", "rate": 0.07353, "desc": "GPT-Image 官方资源"},
    {"value": "Gpt-Image-2", "label": "Gpt-Image-2", "rate": 0.09192, "desc": "GPT-Image-2（Adobe 资源），支持 1k/2k/4k"},
    {"value": "Gpt-Image-3", "label": "Gpt-Image-3", "rate": 0.13787, "desc": "GPT-Image 高倍率分组"},
]

QUALITY_LABELS = {
    "auto": "自动（默认）", "low": "低（草稿）", "medium": "中",
    "high": "高", "xhigh": "超高", "max": "极限",
}


def _caps_for(model_id: str) -> dict:
    """按模型 ID 推断参数能力（来自文档规范 + 令牌模型描述实测）"""
    if "2.5" in model_id:
        return {"n": True, "quality": ["auto", "low", "medium", "high", "xhigh", "max"], "format": True}
    if model_id.endswith("2-c") or "gpt-image-2-c" in model_id:
        # 令牌描述：gpt-image-2-c 暂不支持 n 参数；文档参数表无 quality/format，size 仅 1K 三档
        return {"n": False, "quality": ["auto"], "format": False, "fixed_sizes": list(SIZE_1K_TIERS)}
    if "gpt-image-2" in model_id or "gpt-image-1" in model_id:
        # 文档：quality low/medium/high/auto，format 支持，n 1-10
        return {"n": True, "quality": ["auto", "low", "medium", "high"], "format": True}
    # 未知模型保守处理：不额外传参
    return {"n": True, "quality": ["auto"], "format": False}


def _price_label(pricing_entry: dict | None) -> str:
    if not pricing_entry:
        return ""
    if pricing_entry.get("quota_type") == 1:
        price = pricing_entry.get("model_price") or 0
        return f"${price}/张"
    return "按量计费"


# ── 缓存 + 单飞 ────────────────────────────────────────────────────
_cache: dict = {"data": None, "ts": 0.0}
_lock = asyncio.Lock()


async def _fetch_models(base: str, headers: dict) -> list[dict]:
    """当前令牌可用的图像模型列表"""
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(f"{base}/v1/models", headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(f"/v1/models {resp.status_code}")
    items = resp.json().get("data", []) or []
    out = []
    for m in items:
        if m.get("model_type") == "图像" or "绘画" in str(m.get("tags") or "") or "image" in str(m.get("id") or ""):
            out.append(m)
    return out


async def _fetch_pricing(base: str) -> dict:
    """公开定价数据：按次单价、模型启用分组、分组费率表"""
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(f"{base}/api/pricing")
    if resp.status_code != 200:
        raise RuntimeError(f"/api/pricing {resp.status_code}")
    d = resp.json()
    entries = {}
    for m in d.get("data", []) or []:
        if isinstance(m, dict) and m.get("model_name"):
            entries[m["model_name"]] = m
    return {"entries": entries, "group_ratio": d.get("group_ratio") or {}}


async def _build_catalog() -> dict:
    base = settings.openlux_base_url.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    headers = {"Authorization": f"Bearer {settings.openlux_api_key}"}

    try:
        live_models = await _fetch_models(base, headers)
    except Exception:
        live_models = []
    try:
        pricing = await _fetch_pricing(base)
    except Exception:
        pricing = {"entries": {}, "group_ratio": {}}

    if not live_models:
        return {"models": FALLBACK_MODELS, "groups": FALLBACK_GROUPS, "source": "fallback"}

    entries, group_ratio = pricing["entries"], pricing["group_ratio"]

    # 推荐模型排前面（默认选中第一个）
    PREFERRED_ORDER = ["gpt-image-2.5-flare-c", "gpt-image-2.5-sunburst-c", "gpt-image-2-c"]
    live_models.sort(key=lambda m: (PREFERRED_ORDER.index(m.get("id") or "") if m.get("id") in PREFERRED_ORDER else len(PREFERRED_ORDER), m.get("id") or ""))

    # 组装模型列表
    models = []
    union_groups: list[str] = []
    for m in live_models:
        mid = m.get("id") or ""
        entry = entries.get(mid)
        caps = _caps_for(mid)
        label_base = {
            "gpt-image-2.5-flare-c": "GPT Image 2.5 Flare (推荐)",
            "gpt-image-2.5-sunburst-c": "GPT Image 2.5 Sunburst (精修)",
            "gpt-image-2-c": "GPT Image 2-C",
        }.get(mid, mid)
        price = _price_label(entry)
        label = f"{label_base} · {price}" if price else label_base
        supported = (entry or {}).get("enable_groups") or []
        for g in supported:
            if g not in union_groups:
                union_groups.append(g)
        models.append({
            "value": mid, "label": label, "group": "✨ GPT Image · 即时返回",
            "supported_groups": supported, "capabilities": caps,
            "price": price,
            "description": m.get("description") or "",
        })

    # 分组下拉：仅展示当前可用模型所属分组，按费率升序
    groups = []
    for g in sorted(union_groups, key=lambda x: group_ratio.get(x, 9.99)):
        rate = group_ratio.get(g)
        groups.append({
            "value": g, "label": f"{g} · ×{rate}" if rate is not None else g,
            "rate": rate, "desc": "分组由令牌决定，此处仅用于筛选与费率预估",
        })
    if not groups:
        groups = FALLBACK_GROUPS

    return {"models": models, "groups": groups, "source": "live"}


async def get_catalog(force: bool = False) -> dict:
    """获取模型目录（带 TTL 缓存；force=True 强制刷新）"""
    now = time.time()
    if not force and _cache["data"] and now - _cache["ts"] < TTL:
        return _cache["data"]
    async with _lock:
        now = time.time()
        if not force and _cache["data"] and now - _cache["ts"] < TTL:
            return _cache["data"]
        try:
            data = await _build_catalog()
        except Exception:
            data = {"models": FALLBACK_MODELS, "groups": FALLBACK_GROUPS, "source": "fallback"}
        _cache["data"] = data
        _cache["ts"] = time.time()
        return data


def get_model_caps(model: str) -> dict:
    """同步获取某模型的参数能力（优先缓存，无缓存时用兜底推断）"""
    if _cache["data"]:
        for m in _cache["data"]["models"]:
            if m.get("value") == model:
                return m.get("capabilities") or _caps_for(model)
    return _caps_for(model)


def invalidate_cache() -> None:
    """清空目录缓存。切换 API Key / Base URL 后必须调用，
    否则 10 分钟 TTL 内仍会返回旧令牌的模型列表。"""
    _cache["data"] = None
    _cache["ts"] = 0.0
