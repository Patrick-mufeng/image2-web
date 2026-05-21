"""风格模板 API 路由"""

from fastapi import APIRouter
from backend.services.template_service import get_categories, get_templates, get_template

router = APIRouter()


@router.get("/templates/categories")
async def list_categories():
    """获取模板分类列表"""
    return {"categories": get_categories()}


@router.get("/templates")
async def list_templates(category: str = None):
    """获取模板列表，可按分类过滤"""
    return {"templates": get_templates(category)}


@router.get("/templates/{template_id}")
async def get_template_detail(template_id: str):
    """获取单个模板详情"""
    tpl = get_template(template_id)
    if not tpl:
        return {"error": "模板不存在"}
    return {"template": tpl}
