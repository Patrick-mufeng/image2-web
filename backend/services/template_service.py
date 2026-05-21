"""风格模板库服务 — 读取 style-library.json"""

import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
STYLE_LIB_PATH = os.path.join(DATA_DIR, "style-library.json")


def load_style_library() -> dict:
    """加载风格模板库"""
    if not os.path.exists(STYLE_LIB_PATH):
        return {"categories": [], "templates": [], "styles": [], "scenes": [], "tagLabels": {}}
    with open(STYLE_LIB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_categories() -> list:
    """获取分类列表"""
    lib = load_style_library()
    return lib.get("categories", [])


def get_templates(category: str = None) -> list:
    """获取模板列表，可按分类过滤"""
    lib = load_style_library()
    templates = lib.get("templates", [])
    if category:
        templates = [t for t in templates if t.get("category") == category]
    return templates


def get_template(template_id: str) -> dict:
    """获取单个模板"""
    lib = load_style_library()
    for t in lib.get("templates", []):
        if t.get("id") == template_id:
            return t
    return {}
