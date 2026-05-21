"""文生图 API 路由 — 实时日志架构
- POST /api/generate 立即返回 task_id，后台异步轮询
- GET  /api/task/{id}  前端轮询获取最新状态+日志
- OpenAI 格式：即时返回，但按步骤展示日志
- Replicate 格式：后台轮询，日志逐步追加
"""

import os
import time
import uuid
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException
from backend.config import settings
from backend.models import GenerateRequest, GenerateResponse, ImageInfo
from backend.services.yunwu_client import yunwu_client, YunwuAPIError
from backend.services.log_store import log_store
from backend.services.history_store import history_store
from backend.services.task_manager import task_manager
from backend.routers.config_routes import is_replicate_model, resolve_size

router = APIRouter()


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
    import base64
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


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


@router.post("/generate")
async def generate_image(request: GenerateRequest):
    """文生图 — 立即返回 task_id，后台异步执行"""
    t0 = time.time()

    # 检查 API Key
    if not settings.yunwu_api_key or settings.yunwu_api_key == "sk-your-api-key-here":
        return GenerateResponse(
            success=False,
            error="请先配置 API Key（点击右上角齿轮图标）",
            logs=f"[{ts()}] ❌ API Key 未配置",
            status="failed",
            total_time=0,
        )

    use_replicate = is_replicate_model(request.model)
    task_id = f"task_{uuid.uuid4().hex[:12]}"

    request_data = {
        "model": request.model,
        "aspect_ratio": request.aspect_ratio,
        "megapixels": request.megapixels,
        "num_outputs": request.num_outputs,
        "prompt": request.prompt[:150] + ("..." if len(request.prompt) > 150 else ""),
    }

    if use_replicate:
        # ═══ Replicate 格式：立即返回，后台轮询 ═══
        initial_logs = (
            f"[{ts()}] 🚀 开始生成 (Replicate 异步模式)\n"
            f"[{ts()}] 模型: {request.model}\n"
            f"[{ts()}] 比例: {request.aspect_ratio} | 分辨率: {request.megapixels}MP | 数量: {request.num_outputs}\n"
        )

        # 创建任务状态
        task_manager.create(task_id, {
            "task_id": task_id,
            "status": "pending",
            "logs": initial_logs,
            "output": [],
            "local_images": [],
            "error": None,
            "response_data": {},
            "request_data": request_data,
            "_done": False,
            "_elapsed": 0,
            "_openai": False,
        })

        # 启动后台轮询
        import asyncio
        asyncio.create_task(task_manager.start_replicate_polling(
            task_id=task_id, prompt=request.prompt,
            aspect_ratio=request.aspect_ratio, megapixels=request.megapixels,
            num_outputs=request.num_outputs, output_format=request.output_format,
            output_quality=request.output_quality,
            num_inference_steps=request.num_inference_steps,
            model=request.model, request_data=request_data,
        ))

        return GenerateResponse(
            success=True,
            task_id=task_id,
            status="pending",
            logs=initial_logs,
            request_data=request_data,
            total_time=0,
        )

    else:
        # ═══ OpenAI 格式：同步执行，但按步骤写入日志 ═══
        size = resolve_size(request.aspect_ratio, request.megapixels)
        logs = ""
        logs += f"[{ts()}] 🚀 开始生成 (OpenAI 即时模式)\n"
        logs += f"[{ts()}] 模型: {request.model}\n"
        logs += f"[{ts()}] 尺寸: {size} | 数量: {request.num_outputs}\n"
        logs += f"[{ts()}] 📤 发送请求到 API...\n"

        # 先创建任务状态
        task_manager.create(task_id, {
            "task_id": task_id,
            "status": "processing",
            "logs": logs,
            "output": [],
            "local_images": [],
            "error": None,
            "response_data": {},
            "request_data": request_data,
            "_done": False,
            "_elapsed": 0,
            "_openai": True,
        })

        try:
            result = await yunwu_client.openai_generate(
                prompt=request.prompt, model=request.model,
                size=size, n=request.num_outputs,
            )

            logs += f"[{ts()}] ✅ API 响应成功\n"
            task_manager.append_log(task_id, f"[{ts()}] ✅ API 响应成功")
            task_manager.append_log(task_id, f"[{ts()}] 📥 处理图片...")

            images = []
            history_images = []
            data_items = result.get("data", [])

            for idx, item in enumerate(data_items):
                if item.get("url"):
                    logs += f"[{ts()}] 📥 下载图片 {idx+1}/{len(data_items)}...\n"
                    task_manager.append_log(task_id, f"[{ts()}] 📥 下载图片 {idx+1}/{len(data_items)}...")
                    local_path = await download_image(item["url"], task_id, idx)
                    images.append(ImageInfo(
                        url=item["url"], local_path=local_path,
                        revised_prompt=item.get("revised_prompt", ""),
                    ))
                    history_images.append({
                        "url": item["url"], "local_path": local_path,
                        "revised_prompt": item.get("revised_prompt", ""),
                    })
                elif item.get("b64_json"):
                    logs += f"[{ts()}] 💾 保存 base64 图片 {idx+1}/{len(data_items)}...\n"
                    task_manager.append_log(task_id, f"[{ts()}] 💾 解码 base64 图片 {idx+1}/{len(data_items)}...")
                    local_path = await save_base64_image(item["b64_json"], task_id, idx)
                    images.append(ImageInfo(
                        local_path=local_path,
                        revised_prompt=item.get("revised_prompt", ""),
                    ))
                    history_images.append({
                        "local_path": local_path,
                        "revised_prompt": item.get("revised_prompt", ""),
                    })

            elapsed = time.time() - t0
            logs += f"[{ts()}] ✅ 完成! 耗时: {elapsed:.1f}s\n"

            # 记录历史
            history_store.add({
                "task_id": task_id, "prompt": request.prompt,
                "model": request.model, "aspect_ratio": request.aspect_ratio,
                "megapixels": request.megapixels, "num_outputs": request.num_outputs,
                "size": size, "images": history_images, "status": "succeeded",
            })

            # 更新最终状态
            task_manager._update(task_id, {
                "status": "succeeded",
                "logs": logs,
                "output": [img.url for img in images if img.url],
                "local_images": [img.local_path for img in images if img.local_path],
                "response_data": result,
                "_done": True,
                "_elapsed": elapsed,
            })

            log_store.add({
                "type": "generate", "status": "succeeded",
                "request": request_data, "response_body": result,
                "total_time": elapsed, "error": None,
            })

            return GenerateResponse(
                success=True, task_id=task_id, images=images,
                status="succeeded", logs=logs,
                request_data=request_data, response_data=result,
                total_time=elapsed,
            )

        except YunwuAPIError as e:
            err_log = logs + f"[{ts()}] ❌ API错误: {str(e)[:300]}\n"
            task_manager._update(task_id, {
                "status": "failed", "error": str(e), "logs": err_log, "_done": True,
            })
            log_store.add({
                "type": "generate", "status": "failed",
                "request": request_data, "error": str(e)[:500],
                "total_time": time.time() - t0,
            })
            return GenerateResponse(
                success=False, error=str(e), status="failed",
                logs=err_log, request_data=request_data,
                total_time=time.time() - t0,
            )
        except Exception as e:
            err_log = logs + f"[{ts()}] ❌ 异常: {str(e)[:300]}\n"
            task_manager._update(task_id, {
                "status": "failed", "error": str(e), "logs": err_log, "_done": True,
            })
            return GenerateResponse(
                success=False, error=f"服务器错误: {str(e)}", status="failed",
                logs=err_log, request_data=request_data,
                total_time=time.time() - t0,
            )


@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """实时查询任务状态 — 前端每 500ms 轮询"""
    # 先查内存任务管理器
    task = task_manager.get(task_id)
    if task:
        return {
            "task_id": task_id,
            "status": task.get("status", "unknown"),
            "output": task.get("output", []),
            "local_images": task.get("local_images", []),
            "logs": task.get("logs", ""),
            "error": task.get("error"),
            "response_data": task.get("response_data", {}),
            "request_data": task.get("request_data", {}),
            "_done": task.get("_done", False),
            "_elapsed": task.get("_elapsed", 0),
            "_openai": task.get("_openai", False),
        }

    # 不在内存中 → 尝试查 Replicate API 原始状态（兼容旧任务）
    try:
        data = await yunwu_client.get_prediction(task_id)
        return {
            "task_id": task_id,
            "status": data.get("status", "unknown"),
            "output": data.get("output", []),
            "local_images": [],
            "logs": data.get("logs", ""),
            "error": data.get("error"),
            "response_data": data,
            "_done": data.get("status") in ("succeeded", "failed", "canceled"),
        }
    except YunwuAPIError:
        return {"task_id": task_id, "status": "unknown", "logs": "任务不存在", "_done": True}
    except Exception:
        return {"task_id": task_id, "status": "unknown", "logs": "查询失败", "_done": True}


@router.get("/logs")
async def get_logs(limit: int = 50):
    """获取最近的请求日志"""
    return {"logs": log_store.get_recent(limit)}


@router.delete("/logs")
async def clear_logs():
    """清空日志"""
    log_store.clear()
    return {"success": True}
