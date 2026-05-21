"""FastAPI 应用入口"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.routers import generation, history, config_routes, templates, cases, metadata


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：确保数据目录存在"""
    os.makedirs(settings.data_dir, exist_ok=True)
    os.makedirs(settings.image_save_dir, exist_ok=True)
    os.makedirs("data", exist_ok=True)
    yield


app = FastAPI(
    title="Image2 图片生成工具",
    description="基于云雾API Replicate 格式的 AI 图片生成工具",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 路由
app.include_router(generation.router, prefix="/api", tags=["生图"])
app.include_router(history.router, prefix="/api", tags=["历史"])
app.include_router(config_routes.router, prefix="/api", tags=["配置"])
app.include_router(templates.router, prefix="/api", tags=["模板"])
app.include_router(cases.router, prefix="/api", tags=["案例"])
app.include_router(metadata.router, prefix="/api", tags=["元数据"])

# 静态文件：生成的图片
os.makedirs(settings.image_save_dir, exist_ok=True)
app.mount(
    "/api/images",
    StaticFiles(directory=settings.image_save_dir),
    name="images",
)

# 静态文件：前端 (html=True 使 index.html 在 / 可用)
app.mount("/", StaticFiles(directory="backend/static", html=True), name="static")
