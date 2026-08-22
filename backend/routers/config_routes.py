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

# 模型列表 — group 用于前端 optgroup
# supported_groups 标注该模型在哪些分组下可用
# 来源：OpenLux GET /v1/models 实测（图片相关模型），2026-08
AVAILABLE_MODELS = [
    {"value": "gpt-image-2", "label": "GPT Image 2 (推荐)", "group": "✨ OpenAI 格式 · 即时返回",
     "supported_groups": ["default", "Gpt-Image-2", "Gpt-Image-1"]},
    {"value": "gpt-image-2-c", "label": "GPT Image 2-C", "group": "✨ OpenAI 格式 · 即时返回",
     "supported_groups": ["default", "Gpt-Image-2"]},
    {"value": "gpt-image-1", "label": "GPT Image 1", "group": "✨ OpenAI 格式 · 即时返回",
     "supported_groups": ["default", "Gpt-Image-1"]},
    {"value": "dall-e-3", "label": "DALL-E 3", "group": "✨ OpenAI 格式 · 即时返回",
     "supported_groups": ["default", "Gpt-Image-1"]},
]

# ── 分组定义（16个分组，来源：OpenLux 官方分组参考）───────────────
# 计费 = 模型原价 × 分组倍率（rate）；分组仅用于 UI 过滤与费率展示
GROUP_DEFINITIONS = [
    {"value": "default",     "label": "default 默认",       "rate": 0.07353, "desc": "OpenLux 默认分组，支持 GPT/Claude/图片等全模型", "types": ["openai","image"]},
    {"value": "Gpt-Image-1", "label": "GPT Image 1",        "rate": 0.07353, "desc": "GPT-Image 官方网站资源",                  "types": ["image"]},
    {"value": "Gpt-Image-2", "label": "GPT Image 2",        "rate": 0.09192, "desc": "GPT-Image-2（Adobe 资源）",                 "types": ["image"]},
    {"value": "Doubao-1",    "label": "豆包 1",              "rate": 0.07353, "desc": "豆包/国产模型（自建资源）",               "types": ["image","openai"]},
    {"value": "Doubao-2",    "label": "豆包 2",              "rate": 0.1103,  "desc": "豆包/国产模型",                            "types": ["image","openai"]},
    {"value": "Doubao-3",    "label": "豆包 3",              "rate": 0.22059, "desc": "豆包/国产模型（高倍率）",                 "types": ["image","openai"]},
    {"value": "Wenxin-1",    "label": "文心 1",              "rate": 0.07353, "desc": "文心一言（官方资源）",                    "types": ["image","openai"]},
    {"value": "Wenxin-2",    "label": "文心 2",              "rate": 0.1103,  "desc": "文心一言",                               "types": ["image","openai"]},
    {"value": "Wenxin-3",    "label": "文心 3",              "rate": 0.22059, "desc": "文心一言（高倍率）",                     "types": ["image","openai"]},
    {"value": "Pix-1",       "label": "Pix 即梦",            "rate": 0.07353, "desc": "Pix 资源",                               "types": ["image","video"]},
    {"value": "MJ-1",        "label": "Midjourney Slow",     "rate": 0.04412, "desc": "MJ Slow 慢速出图",                        "types": ["image"]},
    {"value": "MJ-2",        "label": "Midjourney Fast",     "rate": 0.07353, "desc": "MJ Fast 快速出图",                        "types": ["image"]},
    {"value": "Kling-1",     "label": "可灵 1",              "rate": 0.05147, "desc": "可灵 Kling（腾讯资源）",                    "types": ["image","video"]},
    {"value": "Kling-2",     "label": "可灵 2",              "rate": 0.07353, "desc": "可灵 Kling（快手资源）",                    "types": ["image","video"]},
    {"value": "Suno-1",      "label": "Suno 1",              "rate": 0.07353, "desc": "Suno 音乐生成",                            "types": ["music"]},
    {"value": "Suno-2",      "label": "Suno 2",              "rate": 0.1103,  "desc": "Suno 音乐生成",                            "types": ["music"]},
]

OUTPUT_FORMATS = [
    {"value": "jpg", "label": "JPEG"},
    {"value": "png", "label": "PNG"},
    {"value": "webp", "label": "WebP"},
]

# 尺寸映射：aspect_ratio + megapixels → OpenAI size string
SIZE_MAP = {
    ("1:1", "1"): "1024x1024", ("1:1", "2"): "2048x2048", ("1:1", "4"): "4096x4096",
    ("16:9", "1"): "1280x720", ("16:9", "2"): "2560x1440", ("16:9", "4"): "3840x2160",
    ("9:16", "1"): "720x1280", ("9:16", "2"): "1440x2560", ("9:16", "4"): "2160x3840",
    ("4:3", "1"): "1152x864", ("4:3", "2"): "2048x1536", ("4:3", "4"): "4096x3072",
    ("3:4", "1"): "864x1152", ("3:4", "2"): "1536x2048", ("3:4", "4"): "3072x4096",
}


def is_replicate_model(model: str) -> bool:
    """判断模型使用 Replicate 格式还是 OpenAI 格式"""
    return model.startswith("black-forest-labs/") or model.startswith("flux-")


def resolve_size(ratio: str, megapixels: str) -> str:
    """根据比例和分辨率获取 OpenAI size 字符串"""
    return SIZE_MAP.get((ratio, megapixels), "1024x1024")


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
    """获取可用模型列表"""
    return {"models": AVAILABLE_MODELS, "formats": OUTPUT_FORMATS}


@router.get("/config/groups")
async def get_groups():
    """获取可用分组列表"""
    return {"groups": GROUP_DEFINITIONS, "default_group": "default"}


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
    save_settings_to_env(api_key=data.api_key, base_url=data.base_url)
    return {"success": True, "message": "设置已保存，即刻生效"}
