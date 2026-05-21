"""图片元数据处理服务 — EXIF 读写 + PS 预设"""

import os
import json
from datetime import datetime

import piexif
from PIL import Image

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
META_IMAGES_DIR = os.path.join(DATA_DIR, "meta_images")
os.makedirs(META_IMAGES_DIR, exist_ok=True)

# PS 预设模板
PS_PRESETS = [
    {
        "id": "photographer",
        "label": "📷 摄影师",
        "desc": "通用摄影师版权信息",
        "data": {
            "artist": "摄影师姓名",
            "copyright": "Copyright © 2024 摄影师姓名. All rights reserved.",
            "software": "Adobe Photoshop 25.0",
            "description": "专业摄影作品",
        },
    },
    {
        "id": "designer",
        "label": "🎨 设计师",
        "desc": "平面设计师作品信息",
        "data": {
            "artist": "设计师姓名",
            "copyright": "© 2024 设计师姓名",
            "software": "Adobe Photoshop 25.0 / Adobe Illustrator 28.0",
            "description": "平面设计作品",
        },
    },
    {
        "id": "studio",
        "label": "🏢 工作室",
        "desc": "工作室/公司统一版权",
        "data": {
            "artist": "工作室名称",
            "copyright": "Copyright © 2024 工作室名称. All rights reserved.",
            "software": "Adobe Photoshop 25.0",
            "description": "",
        },
    },
    {
        "id": "social",
        "label": "📱 社交媒体",
        "desc": "社交媒体发布用",
        "data": {
            "artist": "用户昵称",
            "copyright": "",
            "software": "Adobe Photoshop 25.0 / Lightroom Classic",
            "description": "发布于社交媒体",
        },
    },
    {
        "id": "clear",
        "label": "🗑️ 清空元数据",
        "desc": "移除所有EXIF信息",
        "data": {
            "artist": "",
            "copyright": "",
            "software": "",
            "description": "",
        },
    },
]

EXIF_TAG_NAMES = {
    "artist": "Artist",
    "copyright": "Copyright",
    "description": "ImageDescription",
    "software": "Software",
    "datetime": "DateTimeOriginal",
}


def exif_to_dict(exif_data: dict) -> dict:
    """将 EXIF 数据转为可读字典"""
    result = {}
    if not exif_data:
        return result
    # IFD0 (主图像信息)
    ifd0 = exif_data.get("0th", {})
    for tag_id, value in ifd0.items():
        name = piexif.TAGS.get(tag_id, {}).get("name", str(tag_id))
        # 处理字节串
        if isinstance(value, bytes):
            try:
                value = value.decode("utf-8").strip("\x00").strip()
            except:
                value = str(value)
        result[name] = str(value)[:100]

    # EXIF 子信息
    exif = exif_data.get("Exif", {})
    for tag_id, value in exif.items():
        name = piexif.TAGS.get(tag_id, {}).get("name", str(tag_id))
        if isinstance(value, bytes):
            try:
                value = value.decode("utf-8").strip("\x00").strip()
            except:
                value = str(value)
        result[name] = str(value)[:100]

    return result


def read_metadata(filepath: str) -> dict:
    """读取图片元数据"""
    info = {"file": os.path.basename(filepath), "size": os.path.getsize(filepath), "exif": {}, "basic": {}}

    # 基础信息
    try:
        img = Image.open(filepath)
        info["basic"] = {
            "format": img.format,
            "mode": img.mode,
            "width": img.width,
            "height": img.height,
        }
    except Exception as e:
        info["basic"] = {"error": str(e)}

    # EXIF
    try:
        exif_dict = piexif.load(filepath)
        info["exif"] = exif_dict_to_flat(exif_dict)
        info["_raw"] = {str(k): str(v)[:200] for k, v in exif_dict.items() if isinstance(v, dict)}
    except Exception:
        info["exif"] = {}

    return info


def exif_dict_to_flat(exif_dict: dict) -> dict:
    """展平 EXIF 字典"""
    flat = {}
    for ifd_name in ("0th", "Exif", "GPS", "Interop", "1st"):
        ifd = exif_dict.get(ifd_name, {})
        for tag, value in ifd.items():
            tag_name = piexif.TAGS.get(tag, {}).get("name", str(tag))
            if isinstance(value, bytes):
                try:
                    value = value.decode("utf-8").strip("\x00").strip()
                except:
                    value = str(value)[:100]
            flat[tag_name] = str(value)[:150]
    return flat


def write_metadata(filepath: str, meta: dict, output_path: str = None) -> str:
    """写入元数据到图片，返回输出路径"""
    if output_path is None:
        name, ext = os.path.splitext(os.path.basename(filepath))
        output_path = os.path.join(META_IMAGES_DIR, f"{name}_modified{ext}")

    # 读取原 EXIF
    try:
        exif_dict = piexif.load(filepath)
    except Exception:
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "Interop": {}, "1st": {}}

    # 映射字段到 EXIF tag
    field_map = {
        "artist": ("0th", piexif.ImageIFD.Artist),
        "copyright": ("0th", piexif.ImageIFD.Copyright),
        "description": ("0th", piexif.ImageIFD.ImageDescription),
        "software": ("0th", piexif.ImageIFD.Software),
    }

    for field, value in meta.items():
        if field in field_map and value:
            ifd_name, tag = field_map[field]
            exif_dict[ifd_name][tag] = value.encode("utf-8")

    # 更新时间
    now = datetime.now().strftime("%Y:%m:%d %H:%M:%S")
    exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = now
    exif_dict["0th"][piexif.ImageIFD.DateTime] = now

    # 写入
    exif_bytes = piexif.dump(exif_dict)
    img = Image.open(filepath)
    img.save(output_path, exif=exif_bytes, quality=95)
    return output_path


def get_presets() -> list:
    """获取 PS 预设列表"""
    return PS_PRESETS
