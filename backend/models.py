"""Pydantic 数据模型"""

from pydantic import BaseModel, Field
from typing import Optional


class ConfigUpdateRequest(BaseModel):
    api_key: str = ""
    base_url: str = ""


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000, description="图像描述文本")
    aspect_ratio: str = Field(default="1:1", description="画面比例")
    megapixels: str = Field(default="1", description="分辨率 (1/2/4)")
    num_outputs: int = Field(default=1, ge=1, le=4, description="生成数量")
    output_format: str = Field(default="jpg", description="输出格式")
    output_quality: int = Field(default=80, ge=1, le=100, description="画质 1-100")
    num_inference_steps: int = Field(default=4, ge=1, le=50, description="推理步数")
    model: str = Field(default="gpt-image-2", description="模型名称")


class ImageInfo(BaseModel):
    url: str = ""
    local_path: str = ""
    revised_prompt: str = ""


class GenerateResponse(BaseModel):
    success: bool
    task_id: str = ""
    images: list[ImageInfo] = []
    error: str = ""
    logs: str = ""
    status: str = ""
    request_data: dict = {}
    response_data: dict = {}
    total_time: float = 0


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    output: list[str] = []
    local_images: list[str] = []
    logs: str = ""
    error: str = ""
    response_data: dict = {}


class HistoryListResponse(BaseModel):
    total: int
    page: int
    limit: int
    records: list[dict]
