"""图片元数据 API 路由 — 读取/写入/批量"""

import os
import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from backend.services.metadata_service import (
    read_metadata,
    write_metadata,
    get_presets,
    save_user_preset,
    delete_user_preset,
    META_IMAGES_DIR,
)

router = APIRouter()

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif"}


@router.get("/metadata/presets")
async def list_presets():
    """获取 PS 预设列表（内置 + 用户自定义）"""
    return {"presets": get_presets()}


class SavePresetRequest(BaseModel):
    label: str
    desc: str = ""
    data: dict


@router.post("/metadata/presets")
async def save_preset(req: SavePresetRequest):
    """保存用户自定义预设"""
    if not req.label.strip():
        return {"success": False, "error": "预设名称不能为空"}
    preset = save_user_preset(req.label.strip(), req.desc, req.data)
    return {"success": True, "preset": preset}


@router.delete("/metadata/presets/{preset_id}")
async def delete_preset(preset_id: str):
    """删除用户自定义预设"""
    ok = delete_user_preset(preset_id)
    return {"success": ok}


@router.post("/metadata/read")
async def read_image_metadata(file: UploadFile = File(...)):
    """上传图片并读取元数据"""
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"不支持的文件格式: {ext}，支持 {', '.join(ALLOWED_EXT)}")

    # 保存临时文件
    os.makedirs(META_IMAGES_DIR, exist_ok=True)
    tmp_path = os.path.join(META_IMAGES_DIR, f"tmp_{uuid.uuid4().hex}{ext}")
    content = await file.read()
    with open(tmp_path, "wb") as f:
        f.write(content)

    # 读取元数据
    info = read_metadata(tmp_path)
    info["tmp_path"] = tmp_path
    return info


@router.post("/metadata/write")
async def write_image_metadata(
    tmp_path: str = Form(...),
    artist: str = Form(""),
    copyright: str = Form(""),
    description: str = Form(""),
    software: str = Form(""),
):
    """写入元数据并返回修改后的图片"""
    if not os.path.exists(tmp_path):
        raise HTTPException(404, "临时文件不存在，请重新上传")

    meta = {"artist": artist, "copyright": copyright, "description": description, "software": software}

    try:
        output_path = write_metadata(tmp_path, meta)
        filename = os.path.basename(output_path)
        return {"download_url": f"/api/meta-download/{filename}", "filepath": output_path}
    except Exception as e:
        raise HTTPException(500, f"写入元数据失败: {str(e)}")


@router.post("/metadata/batch")
async def batch_write_metadata(
    files: list[UploadFile] = File(...),
    artist: str = Form(""),
    copyright: str = Form(""),
    description: str = Form(""),
    software: str = Form(""),
):
    """批量写入元数据并打包下载"""
    import zipfile
    import shutil

    os.makedirs(META_IMAGES_DIR, exist_ok=True)
    batch_dir = os.path.join(META_IMAGES_DIR, f"batch_{uuid.uuid4().hex}")
    os.makedirs(batch_dir, exist_ok=True)

    meta = {"artist": artist, "copyright": copyright, "description": description, "software": software}
    results = []

    for file in files:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_EXT:
            continue
        tmp_path = os.path.join(batch_dir, file.filename)
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)
        try:
            out_path = write_metadata(tmp_path, meta)
            results.append({"file": file.filename, "status": "ok", "output": os.path.basename(out_path)})
        except Exception as e:
            results.append({"file": file.filename, "status": "error", "error": str(e)})

    # 打包成 zip
    zip_path = os.path.join(META_IMAGES_DIR, f"batch_{uuid.uuid4().hex}.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        for r in results:
            if r["status"] == "ok":
                out_file = os.path.join(batch_dir, r["output"])
                if not os.path.exists(out_file):
                    out_file = os.path.join(META_IMAGES_DIR, r["output"])
                if os.path.exists(out_file):
                    zf.write(out_file, r["output"])

    # 清理
    shutil.rmtree(batch_dir, ignore_errors=True)

    return {"download_url": f"/api/meta-download/{os.path.basename(zip_path)}", "results": results}


@router.get("/meta-download/{filename}")
async def download_meta_file(filename: str):
    """下载处理后的文件"""
    filepath = os.path.join(META_IMAGES_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(404, "文件不存在")
    media_type = "image/jpeg"
    if filename.endswith(".png"):
        media_type = "image/png"
    elif filename.endswith(".webp"):
        media_type = "image/webp"
    elif filename.endswith(".zip"):
        media_type = "application/zip"
    return FileResponse(filepath, media_type=media_type, filename=filename)
