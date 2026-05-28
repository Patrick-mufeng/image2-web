"""应用配置管理 — 从 .env 文件加载，支持动态更新"""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    yunwu_api_key: str = ""
    yunwu_base_url: str = "https://yunwu.ai"
    host: str = "0.0.0.0"
    port: int = 8000
    data_dir: str = "data"
    image_save_dir: str = "data/images"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()


def reload_settings():
    """重新加载 .env 文件中的配置"""
    from dotenv import load_dotenv
    load_dotenv(".env", override=True)
    settings.yunwu_api_key = os.getenv("YUNWU_API_KEY", "")
    settings.yunwu_base_url = os.getenv("YUNWU_BASE_URL", "https://yunwu.ai")


def save_settings_to_env(api_key: str = "", base_url: str = ""):
    """保存配置到 .env 文件并立即生效（保留所有已有键）"""
    env_path = ".env"

    existing = {}
    existing_order = []  # 保留原始顺序
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    key, _, val = stripped.partition("=")
                    key = key.strip()
                    val = val.strip()
                    existing[key] = val
                    existing_order.append(key)

    # 更新需要修改的键
    if api_key:
        existing["YUNWU_API_KEY"] = api_key
    if base_url:
        existing["YUNWU_BASE_URL"] = base_url
    existing["HOST"] = str(settings.host)
    existing["PORT"] = str(settings.port)

    # 确保 4 个关键键在写入列表中
    for k in ["YUNWU_API_KEY", "YUNWU_BASE_URL", "HOST", "PORT"]:
        if k not in existing_order:
            existing_order.append(k)

    with open(env_path, "w", encoding="utf-8") as f:
        f.write("# 云雾API 配置\n")
        for key in existing_order:
            if key in existing:
                f.write(f"{key}={existing[key]}\n")

    # 动态更新当前配置
    if api_key:
        settings.yunwu_api_key = api_key
    if base_url:
        settings.yunwu_base_url = base_url
