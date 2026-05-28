"""图生图 API 路由
- POST /api/edits  上传图片+prompt，调用图生图编辑接口
  支持单图编辑、多图编辑、蒙版编辑
"""

import os
import time
import base64
import uuid
import traceback
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
    n: int = Form(1, ge=1, le=4),
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

        # 调用编辑 API（逐张处理多图）
        all_results = []
        for img_idx, (img_filename, img_data) in enumerate(image_datas):
            if len(image_datas) > 1:
                logs += f"[{_ts()}] 📤 处理图片 {img_idx+1}/{len(image_datas)}: {img_filename}\n"
            result = await yunwu_client.edit_image(
                image_data=img_data,
                prompt=prompt,
                filename=img_filename,
                model=model,
                mask_data=mask_data,
                mask_filename=mask_filename,
                n=n,
                size=size,
                quality=quality,
                background=background,
            )
            all_results.append(result)

        logs += f"[{_ts()}] ✅ API 响应成功\n"

        # 处理结果
        task_id = f"edit_{uuid.uuid4().hex[:12]}"
        save_dir = settings.image_save_dir
        os.makedirs(save_dir, exist_ok=True)

        images_out = []
        history_images = []

        def _save_b64(b64_str: str, idx: int) -> str:
            fname = f"{task_id}_{idx}.png"
            fpath = os.path.join(save_dir, fname)
            raw = base64.b64decode(b64_str)
            with open(fpath, "wb") as f:
                f.write(raw)
            return f"/api/images/{fname}"

        img_counter = 0
        for result in all_results:
            # edits 接口返回 b64_json
            data_field = result.get("data", {})
            if isinstance(data_field, dict) and data_field.get("b64_json"):
                logs += f"[{_ts()}] 💾 保存图片 {img_counter+1}...\n"
                local_path = _save_b64(data_field["b64_json"], img_counter)
                images_out.append({"local_path": local_path, "revised_prompt": ""})
                history_images.append({"local_path": local_path, "revised_prompt": ""})
                img_counter += 1
            elif isinstance(data_field, list):
                for item in data_field:
                    if isinstance(item, dict) and item.get("b64_json"):
                        logs += f"[{_ts()}] 💾 保存图片 {img_counter+1}/{img_counter+len(data_field)}...\n"
                        local_path = _save_b64(item["b64_json"], img_counter)
                        images_out.append({"local_path": local_path, "revised_prompt": item.get("revised_prompt", "")})
                        history_images.append({"local_path": local_path, "revised_prompt": item.get("revised_prompt", "")})
                        img_counter += 1

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
            "request": {"prompt": prompt[:150], "model": model, "size": size, "n": n, "image_count": len(images)},
            "response_body": all_results[0] if all_results else {},
            "total_time": elapsed,
            "error": None,
        })

        return {
            "success": True,
            "task_id": task_id,
            "images": images_out,
            "status": "succeeded",
            "logs": logs,
            "response_data": all_results[0] if all_results else {},
            "total_time": elapsed,
        }

    except YunwuAPIError as e:
        error_log = logs + f"[{_ts()}] ❌ API错误: {str(e)}\n"
        err_detail = e.to_dict() if hasattr(e, 'to_dict') else {"error": str(e)}
        from backend.services.log_store import log_store
        log_store.save_entry({
            "type": "edit", "status": "failed",
            "request": {"prompt": prompt[:150], "model": model},
            "error": str(e)[:500], "error_detail": err_detail,
            "total_time": time.time() - t0,
        })
        return {"success": False, "error": str(e), "status": "failed", "logs": error_log, "total_time": round(time.time() - t0, 1)}
    except Exception as e:
        full_tb = traceback.format_exc()
        error_log = logs + f"[{_ts()}] ❌ 异常: {str(e)}\n"
        error_log += f"[{_ts()}] 📋 堆栈: {full_tb[-500:]}\n"
        return {"success": False, "error": f"服务器错误: {str(e)}", "status": "failed", "logs": error_log, "total_time": round(time.time() - t0, 1)}
