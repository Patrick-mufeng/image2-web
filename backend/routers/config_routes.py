"""配置相关 API 路由"""

import os
import time
import httpx
from fastapi import APIRouter
from pydantic import BaseModel
from backend.config import settings, save_settings_to_env

router = APIRouter()

ASPECT_RATIO_OPTIONS = [
    {"ratio": "1:1", "label": "1:1 正方形", "icon": "⊞"},
    {"ratio": "16:9", "label": "16:9 宽屏", "icon": "▬"},
    {"ratio": "9:16", "label": "9:16 竖屏", "icon": "▮"},
    {"ratio": "4:3", "label": "4:3 横向", "icon": "▭"},
    {"ratio": "3:4", "label": "3:4 竖向", "icon": "▯"},
]

RESOLUTION_OPTIONS = [
    {"value": "1", "label": "标准 (1MP)", "desc": "快速生成"},
    {"value": "2", "label": "2K (~2MP)", "desc": "高清画质"},
    {"value": "4", "label": "4K (~4MP)", "desc": "超清画质"},
]

# 模型与分组的权威数据来自 model_catalog（/v1/models + /api/pricing 动态拉取），
# 这里的常量仅作拉取失败时的兜底。
from backend.services.model_catalog import FALLBACK_GROUPS as GROUP_DEFINITIONS, FALLBACK_MODELS as AVAILABLE_MODELS
from backend.services.model_catalog import get_catalog

OUTPUT_FORMATS = [
    {"value": "jpg", "label": "JPEG"},
    {"value": "png", "label": "PNG"},
    {"value": "webp", "label": "WebP"},
]

# 尺寸映射：aspect_ratio + megapixels → OpenAI size string
# gpt-image-2 / 2.5 的硬限制：最大边 ≤3840、宽高均为 16px 倍数、长宽比 ≤3:1、
# 总像素 655,360 ~ 8,294,400（= 3840×2160）。4MP 档据此取合规最大值。
SIZE_MAP = {
    ("1:1", "1"): "1024x1024", ("1:1", "2"): "2048x2048", ("1:1", "4"): "2880x2880",
    ("16:9", "1"): "1280x720", ("16:9", "2"): "2560x1440", ("16:9", "4"): "3840x2160",
    ("9:16", "1"): "720x1280", ("9:16", "2"): "1440x2560", ("9:16", "4"): "2160x3840",
    ("4:3", "1"): "1152x864", ("4:3", "2"): "2048x1536", ("4:3", "4"): "3264x2448",
    ("3:4", "1"): "864x1152", ("3:4", "2"): "1536x2048", ("3:4", "4"): "2448x3264",
}


def is_replicate_model(model: str) -> bool:
    """判断模型使用 Replicate 格式还是 OpenAI 格式"""
    return model.startswith("black-forest-labs/") or model.startswith("flux-")


def resolve_size(ratio: str, megapixels: str) -> str:
    """根据比例和分辨率获取 OpenAI size 字符串"""
    return SIZE_MAP.get((ratio, megapixels), "1024x1024")


def resolve_size_for_caps(ratio: str, megapixels: str, caps: dict | None) -> tuple[str, bool]:
    """按模型能力解析尺寸。模型仅支持固定档位时（如 gpt-image-2-c 的 1K 三档），
    按比例方向收敛到最接近的档位。返回 (size, 是否被收敛)。"""
    fixed = (caps or {}).get("fixed_sizes") or []
    if not fixed:
        return resolve_size(ratio, megapixels), False
    if ratio == "1:1" and "1024x1024" in fixed:
        return "1024x1024", True
    try:
        w, h = (int(x) for x in ratio.split(":"))
    except ValueError:
        w, h = 1, 1
    if w >= h:
        return ("1536x1024" if "1536x1024" in fixed else fixed[0]), True
    return ("1024x1536" if "1024x1536" in fixed else fixed[-1]), True


class SettingsUpdateRequest(BaseModel):
    api_key: str = ""
    base_url: str = ""


@router.get("/config/balance")
async def get_balance():
    """查询 API Key 余额（OpenLux 支持 OpenAI 风格订阅/用量接口）"""
    if not settings.openlux_api_key or settings.openlux_api_key == "sk-your-api-key-here":
        return {"configured": False, "error": "API Key 未配置"}

    base_url = settings.openlux_base_url.rstrip("/")
    if base_url.endswith("/v1"):
        base_url = base_url[:-3]
    headers = {
        "Authorization": f"Bearer {settings.openlux_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. 查询订阅信息（令牌名、总额度）
            sub_resp = await client.get(
                f"{base_url}/v1/dashboard/billing/subscription",
                headers=headers,
            )
            if sub_resp.status_code != 200:
                return {"configured": True, "error": f"查询失败 ({sub_resp.status_code})"}

            sub_data = sub_resp.json()
            token_name = sub_data.get("token_name", "")
            soft_limit = sub_data.get("soft_limit_usd", 0)

            # 2. 查询本月用量
            now = int(time.time())
            # 当前月第一天
            from datetime import datetime, timezone
            dt = datetime.fromtimestamp(now, tz=timezone.utc)
            month_start = int(datetime(dt.year, dt.month, 1, tzinfo=timezone.utc).timestamp())

            usage_resp = await client.get(
                f"{base_url}/v1/dashboard/billing/usage",
                headers=headers,
                params={"start": month_start, "end": now},
            )

            total_usage = 0
            if usage_resp.status_code == 200:
                usage_data = usage_resp.json()
                total_usage = usage_data.get("total_usage", 0)

            # 3. 合成结果
            # soft_limit=100000000 表示不限量，显示实际用量
            is_unlimited = soft_limit >= 99999999

            return {
                "configured": True,
                "token_name": token_name,
                "total_usage": round(total_usage, 4),
                "soft_limit": soft_limit,
                "is_unlimited": is_unlimited,
                "remaining": "不限量" if is_unlimited else round(max(0, soft_limit - total_usage), 4),
            }

    except httpx.ConnectError:
        return {"configured": True, "error": "无法连接到服务器，请检查 Base URL"}
    except httpx.TimeoutException:
        return {"configured": True, "error": "查询超时，请稍后重试"}
    except Exception as e:
        return {"configured": True, "error": f"查询异常: {str(e)[:100]}"}


@router.get("/config/aspect-ratios")
async def get_aspect_ratios():
    """获取支持的比例列表"""
    return {"ratios": ASPECT_RATIO_OPTIONS}


@router.get("/config/resolutions")
async def get_resolutions():
    """获取支持的分辨率选项"""
    return {"resolutions": RESOLUTION_OPTIONS}


@router.get("/config/models")
async def get_models():
    """获取可用模型列表 — 优先线上动态目录（令牌实际可用 + 定价），失败回退内置表"""
    catalog = await get_catalog()
    return {"models": catalog["models"], "formats": OUTPUT_FORMATS, "source": catalog["source"]}


@router.get("/config/groups")
async def get_groups():
    """获取分组列表 — 优先线上动态目录（当前可用模型所属分组 + 实时费率）"""
    catalog = await get_catalog()
    return {"groups": catalog["groups"], "default_group": catalog["groups"][0]["value"] if catalog["groups"] else "default",
            "source": catalog["source"]}


@router.get("/config/status")
async def get_status():
    """检查 API Key 配置状态"""
    configured = bool(settings.openlux_api_key) and settings.openlux_api_key != "sk-your-api-key-here"
    return {
        "api_configured": configured,
        "message": "API 已配置" if configured else "请配置 API Key",
    }


@router.get("/config/settings")
async def get_settings():
    """获取当前设置"""
    return {
        "api_key": settings.openlux_api_key,
        "base_url": settings.openlux_base_url,
        "host": settings.host,
        "port": settings.port,
    }


@router.post("/config/settings")
async def save_settings(data: SettingsUpdateRequest):
    """保存设置到 .env 文件并立即生效"""
    from backend.services.model_catalog import invalidate_cache
    save_settings_to_env(api_key=data.api_key, base_url=data.base_url)
    # Key/地址变更后清空模型目录缓存，下次请求按新令牌重建（单飞锁内同步完成）
    invalidate_cache()
    return {"success": True, "message": "设置已保存，即刻生效"}
