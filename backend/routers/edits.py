"""图生图 API 路由
- POST /api/edits  上传图片+prompt，调用图生图编辑接口
  支持单图编辑、多图编辑、蒙版编辑
"""

import os
import time
import base64
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from backend.config import settings
from backend.services.yunwu_client import yunwu_client, YunwuAPIError
from backend.services.history_store import history_store
from backend.routers.config_routes import is_replicate_model, resolve_size

router = APIRouter()


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


@router.post("/edits")
async def edit_image(
    prompt: str = Form(..., min_length=1, max_length=4000),
    model: str = Form("gpt-image-2"),
    size: str = Form("1024x1024"),
    n: int = Form(1, ge=1, le=10),
    quality: str = Form("auto"),
    background: str = Form("auto"),
    images: list[UploadFile] = File(..., description="图片文件，1-16张"),
    mask: UploadFile | None = File(None, description="蒙版图片（PNG）"),
):
    """图生图 — 上传图片 + prompt，返回编辑结果"""
    t0 = time.time()

    # 检查 API Key
    if not settings.yunwu_api_key or settings.yunwu_api_key == "sk-your-api-key-here":
        return {
            "success": False,
            "error": "请先配置 API Key（点击右上角齿轮图标）",
            "status": "failed",
            "total_time": 0,
        }

    if len(images) > 16:
        return {"success": False, "error": "最多上传 16 张图片", "status": "failed"}

    if not images:
        return {"success": False, "error": "请至少上传一张图片", "status": "failed"}

    logs = f"[{_ts()}] 🖼️ 开始图生图编辑\n"
    logs += f"[{_ts()}] 模型: {model} | 图片: {len(images)} 张 | 尺寸: {size}\n"

    try:
        # 读取上传的图片数据
        image_datas = []
        for img in images:
            data = await img.read()
            if len(data) == 0:
                return {"success": False, "error": f"图片 '{img.filename}' 为空", "status": "failed"}
            image_datas.append((img.filename or "image.png", data))

        logs += f"[{_ts()}] 📤 上传到 API...\n"

        # 读取蒙版（如果有）
        mask_data = None
        mask_filename = "mask.png"
        if mask:
            mask_data = await mask.read()
            if len(mask_data) > 0:
                logs += f"[{_ts()}] 🎭 使用蒙版\n"
            else:
                mask_data = None

        # 调用编辑 API
        result = await yunwu_client.edit_image(
            image_data=image_datas[0][1],
            prompt=prompt,
            filename=image_datas[0][0],
            model=model,
            mask_data=mask_data,
            mask_filename=mask_filename,
            n=n,
            size=size,
            quality=quality,
            background=background,
        )

        logs += f"[{_ts()}] ✅ API 响应成功\n"

        # 处理结果
        task_id = f"edit_{uuid.uuid4().hex[:12]}"
        save_dir = settings.image_save_dir
        os.makedirs(save_dir, exist_ok=True)

        images_out = []
        history_images = []

        # edits 接口返回 b64_json
        data_field = result.get("data", {})
        if isinstance(data_field, dict) and data_field.get("b64_json"):
            # 单张图片
            logs += f"[{_ts()}] 💾 保存图片...\n"
            filename = f"{task_id}_0.png"
            filepath = os.path.join(save_dir, filename)
            raw = base64.b64decode(data_field["b64_json"])
            with open(filepath, "wb") as f:
                f.write(raw)
            local_path = f"/api/images/{filename}"
            images_out.append({"local_path": local_path, "revised_prompt": ""})
            history_images.append({"local_path": local_path, "revised_prompt": ""})
        elif isinstance(data_field, list):
            # 多张图片
            for idx, item in enumerate(data_field):
                if isinstance(item, dict) and item.get("b64_json"):
                    logs += f"[{_ts()}] 💾 保存图片 {idx+1}/{len(data_field)}...\n"
                    filename = f"{task_id}_{idx}.png"
                    filepath = os.path.join(save_dir, filename)
                    raw = base64.b64decode(item["b64_json"])
                    with open(filepath, "wb") as f:
                        f.write(raw)
                    local_path = f"/api/images/{filename}"
                    images_out.append({"local_path": local_path, "revised_prompt": item.get("revised_prompt", "")})
                    history_images.append({"local_path": local_path, "revised_prompt": item.get("revised_prompt", "")})

        elapsed = time.time() - t0
        logs += f"[{_ts()}] ✅ 完成! 耗时: {elapsed:.1f}s\n"

        # 记录历史
        history_store.add({
            "task_id": task_id,
            "prompt": prompt,
            "model": model,
            "aspect_ratio": "edit",
            "megapixels": size,
            "num_outputs": n,
            "size": size,
            "images": history_images,
            "status": "succeeded",
            "edit_mode": True,
        })

        # 记录监控日志
        from backend.services.log_store import log_store
        log_store.add({
            "type": "edit",
            "status": "succeeded",
            "request": {"prompt": prompt[:150], "model": model, "size": size, "n": n},
            "response_body": result,
            "total_time": elapsed,
            "error": None,
        })

        return {
            "success": True,
            "task_id": task_id,
            "images": images_out,
            "status": "succeeded",
            "logs": logs,
            "response_data": result,
            "total_time": elapsed,
        }

    except YunwuAPIError as e:
        error_log = logs + f"[{_ts()}] ❌ API错误: {str(e)[:300]}\n"
        err_detail = e.to_dict() if hasattr(e, 'to_dict') else {"error": str(e)}
        from backend.services.log_store import log_store
        log_store.save_entry({
            "type": "edit", "status": "failed",
            "request": {"prompt": prompt[:150], "model": model},
            "error": str(e)[:500], "error_detail": err_detail,
            "total_time": time.time() - t0,
        })
        return {"success": False, "error": str(e), "status": "failed", "logs": error_log, "total_time": time.time() - t0}
    except Exception as e:
        error_log = logs + f"[{_ts()}] ❌ 异常: {str(e)[:300]}\n"
        return {"success": False, "error": f"服务器错误: {str(e)}", "status": "failed", "logs": error_log, "total_time": time.time() - t0}
