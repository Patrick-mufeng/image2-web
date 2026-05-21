"""历史记录 API 路由"""

from fastapi import APIRouter, Query
from backend.services.history_store import history_store
from backend.models import HistoryListResponse

router = APIRouter()


@router.get("/history", response_model=HistoryListResponse)
async def get_history(page: int = Query(1, ge=1), limit: int = Query(12, ge=1, le=50)):
    """获取生成历史（分页）"""
    return history_store.list(page=page, limit=limit)


@router.get("/history/all")
async def get_all_history():
    """获取全部历史"""
    records = history_store._read() if hasattr(history_store, '_read') else []
    return {"total": len(records), "records": records}


@router.delete("/history")
async def clear_history():
    """清空历史记录"""
    history_store.clear()
    return {"success": True, "message": "历史记录已清空"}
